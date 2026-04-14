"""MEM-001: 대화 메모리 관리"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from config.settings import SESSIONS_DIR


class ConversationMemory:
    def __init__(self, max_turns: int = 20):
        self.messages: list[dict] = []
        self.max_turns = max_turns
        self._dir = Path(SESSIONS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        # 최대 턴 수 초과 시 오래된 메시지 제거
        limit = self.max_turns * 2
        if len(self.messages) > limit:
            self.messages = self.messages[-limit:]

    def get_recent(self, n: int = 10) -> list[dict]:
        """최근 n턴 반환"""
        return self.messages[-(n * 2):]

    def clear(self) -> None:
        self.messages = []

    def save(self, name: str | None = None) -> str:
        name = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._dir / f"{name}.json"
        path.write_text(
            json.dumps(self.messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def load(self, name: str) -> bool:
        path = self._dir / f"{name}.json"
        if not path.exists():
            return False
        self.messages = json.loads(path.read_text(encoding="utf-8"))
        return True

    def list_sessions(self) -> list[str]:
        return sorted(
            [p.stem for p in self._dir.glob("*.json")],
            reverse=True,
        )

    @property
    def turn_count(self) -> int:
        return len(self.messages) // 2
