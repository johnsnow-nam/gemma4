"""BRAIN-001: Gemma4 AI 추론 엔진"""
from __future__ import annotations
import base64
import logging

import ollama

from agent.memory import ConversationMemory
from config.settings import OLLAMA_URL, DEFAULT_MODEL

logger = logging.getLogger(__name__)

_client = ollama.Client(host=OLLAMA_URL)


class AgentBrain:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.memory = ConversationMemory(max_turns=20)

    # ──────────────────────────────────────────────
    def think(
        self,
        user_input: str,
        context: str = "",
        system_prompt: str = "",
        remember: bool = True,
    ) -> str:
        """Gemma4 추론 (동기)"""
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 이전 대화 포함
        messages.extend(self.memory.get_recent(10))

        # 파일 컨텍스트 + 사용자 입력 결합
        full_input = f"{context}\n\n{user_input}".strip() if context else user_input
        messages.append({"role": "user", "content": full_input})

        try:
            resp = _client.chat(
                model=self.model,
                messages=messages,
                stream=False,
                options={"temperature": 0.3},
            )
            reply: str = resp.message.content
        except Exception as e:
            logger.error("Ollama 오류: %s", e)
            return f"⚠️ AI 오류: {e}"

        if remember:
            self.memory.add("user", full_input)
            self.memory.add("assistant", reply)

        return reply

    # ──────────────────────────────────────────────
    def think_with_image(self, prompt: str, image_path: str) -> str:
        """이미지 포함 추론 (vision)"""
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            resp = _client.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [img_b64],
                }],
                stream=False,
                options={"temperature": 0.3},
            )
            reply = resp.message.content
            self.memory.add("user", f"[이미지] {prompt}")
            self.memory.add("assistant", reply)
            return reply
        except Exception as e:
            return f"⚠️ 이미지 분석 오류: {e}"

    # ──────────────────────────────────────────────
    def get_status(self) -> dict:
        """Ollama 연결 상태 확인"""
        try:
            resp = _client.list()
            raw = resp.models if hasattr(resp, "models") else resp.get("models", [])
            models = [m.model if hasattr(m, "model") else m.get("name", "?") for m in raw]
            return {"ok": True, "models": models}
        except Exception as e:
            return {"ok": False, "error": str(e)}
