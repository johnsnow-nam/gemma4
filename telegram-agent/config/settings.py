"""에이전트 전역 설정"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ── 텔레그램
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID: int = int(os.getenv("ALLOWED_USER_ID", "0"))

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
