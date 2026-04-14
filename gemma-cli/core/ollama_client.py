"""Ollama API 클라이언트 — 스트리밍 채팅 지원"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Generator, Iterator

import ollama


class OllamaClient:
    def __init__(
        self,
        model: str = "gemma4:26b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        num_ctx: int = 8192,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self._client = ollama.Client(host=base_url)

    # ------------------------------------------------------------------
    def list_models(self) -> list[dict]:
        """모델 목록 반환 — {name, size} dict 리스트"""
        try:
            resp = self._client.list()
            models = resp.models if hasattr(resp, "models") else resp.get("models", [])
            result = []
            for m in models:
                if hasattr(m, "model"):          # ollama >= 0.4 객체 방식
                    result.append({"name": m.model, "size": m.size or 0})
                else:                            # dict 방식 (구버전 호환)
                    result.append({"name": m.get("name", "?"), "size": m.get("size", 0)})
            return result
        except Exception:
            return []

    def is_model_available(self, model: str) -> bool:
        return any(m["name"].startswith(model) for m in self.list_models())

    # ------------------------------------------------------------------
    def _options(self, temperature: float | None = None, num_ctx: int | None = None) -> dict:
        return {
            "temperature": temperature if temperature is not None else self.temperature,
            "num_ctx": num_ctx if num_ctx is not None else self.num_ctx,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
        }

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        num_ctx: int | None = None,
    ) -> Iterator[str]:
        """스트리밍 채팅 — 토큰 단위 yield"""
        stream = self._client.chat(
            model=self.model,
            messages=messages,
            stream=True,
            options=self._options(temperature, num_ctx),
        )
        for chunk in stream:
            if hasattr(chunk, "message"):
                token = chunk.message.content or ""
            else:
                token = chunk.get("message", {}).get("content", "")
            if token:
                yield token

    # ------------------------------------------------------------------
    @staticmethod
    def encode_image(path: str | Path) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # ------------------------------------------------------------------
    def chat_stream_with_images(
        self,
        messages: list[dict],
        image_paths: list[str | Path],
        temperature: float | None = None,
        num_ctx: int | None = None,
    ) -> Iterator[str]:
        """이미지가 포함된 스트리밍 채팅"""
        images_b64 = [self.encode_image(p) for p in image_paths]
        # 마지막 user 메시지에 이미지 첨부
        msg_copy = [m.copy() for m in messages]
        for m in reversed(msg_copy):
            if m["role"] == "user":
                m["images"] = images_b64
                break
        stream = self._client.chat(
            model=self.model,
            messages=msg_copy,
            stream=True,
            options=self._options(temperature, num_ctx),
        )
        for chunk in stream:
            if hasattr(chunk, "message"):
                token = chunk.message.content or ""
            else:
                token = chunk.get("message", {}).get("content", "")
            if token:
                yield token

    def chat_once(self, messages: list[dict]) -> str:
        """비스트리밍 단일 응답 (요약 등 내부 사용)"""
        resp = self._client.chat(
            model=self.model,
            messages=messages,
            stream=False,
            options=self._options(),
        )
        if hasattr(resp, "message"):
            return resp.message.content or ""
        return resp.get("message", {}).get("content", "")
