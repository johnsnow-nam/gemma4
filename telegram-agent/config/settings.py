"""에이전트 전역 설정"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ── 텔레그램
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# 단일 ID 또는 쉼표 구분 복수 ID 지원 (예: "111,222,333")
_raw_ids = os.getenv("ALLOWED_USER_IDS", os.getenv("ALLOWED_USER_ID", "0"))
ALLOWED_USER_IDS: set[int] = {
    int(x.strip()) for x in _raw_ids.split(",") if x.strip().isdigit()
}
ALLOWED_USER_ID: int = next(iter(ALLOWED_USER_IDS), 0)  # 하위 호환

# ── Ollama
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemma4:26b")

# ── 경로
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROJECTS_YAML = os.path.join(BASE_DIR, "config", "projects.yaml")
SESSIONS_DIR = os.path.expanduser("~/.telegram-agent/sessions")
TEMP_DIR = os.path.expanduser("~/.telegram-agent/tmp")

# ── 제한
MAX_REPLY_LENGTH = 4000   # 텔레그램 메시지 최대 길이
MAX_FILE_LINES = 500
MAX_PROJECT_FILES = 20
SHELL_TIMEOUT = 120       # 빌드용 넉넉한 타임아웃

# ── 차단 명령어
BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf ~", "sudo rm", "mkfs",
    "dd if=", ":(){:|:&};:", "chmod -R 777 /",
]
