"""대화 세션 관리 — D-001, D-002, D-003"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".gemma-cli" / "sessions"

SYSTEM_PROMPT = """당신은 gemma-cli 로컬 AI 어시스턴트입니다.
사용자의 코드, 파일, 프로젝트를 분석하고 도움을 드립니다.
한국어로 대화하며, 코드는 항상 마크다운 코드블록으로 작성합니다.
파일 내용이 제공되면 그것을 기반으로 정확한 분석을 합니다."""


class Session:
    def __init__(self, model: str = "gemma4:26b"):
        self.model = model
        self.messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.created_at = datetime.now()
        self.name: str | None = None

    # ------------------------------------------------------------------
    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def clear(self) -> None:
        """대화 초기화 — 시스템 프롬프트 유지"""
        self.messages = [self.messages[0]]

    def token_estimate(self) -> int:
        """간단한 토큰 수 추정 (글자 수 / 4)"""
        total = sum(len(m["content"]) for m in self.messages)
        return total // 4

    # ------------------------------------------------------------------
    def save(self, name: str) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "name": name,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "messages": self.messages,
        }
        path = SESSIONS_DIR / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.name = name
        return path

    @classmethod
    def load(cls, name: str) -> "Session":
        path = SESSIONS_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"세션을 찾을 수 없습니다: {name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        s = cls(model=data["model"])
        s.messages = data["messages"]
        s.name = data["name"]
        return s

    @staticmethod
    def list_sessions() -> list[str]:
        if not SESSIONS_DIR.exists():
            return []
        return [p.stem for p in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)]
