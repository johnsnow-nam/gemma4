"""MCP 서버 설정"""
from __future__ import annotations
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "gemma4:26b")
DEFAULT_TEMPERATURE = float(os.environ.get("DEFAULT_TEMPERATURE", "0.3"))

# 쓰기 허용 경로 (홈 폴더 이하만)
HOME = os.path.expanduser("~")
ALLOWED_WRITE_PREFIXES = [HOME]

# 시스템 경로 차단
BLOCKED_WRITE_PREFIXES = ["/etc", "/usr", "/sys", "/proc", "/dev", "/boot", "/bin", "/sbin", "/lib"]

# 위험 셸 명령어
DANGEROUS_SHELL_PATTERNS = [
    "rm -rf /", "rm -rf ~", "dd if=", "mkfs", "> /dev/",
    ":(){ :|:& };:", "chmod -R 777 /", "sudo rm", "sudo dd",
    "wget.*|.*sh", "curl.*|.*sh",
]
BLOCKED_SHELL_PREFIXES = ["sudo "]

SHELL_TIMEOUT = int(os.environ.get("SHELL_TIMEOUT", "30"))
MAX_FILE_SIZE_KB = 500
MAX_FOLDER_FILES = 50
MAX_SEARCH_RESULTS = 100

# 최근 파일 추적
RECENT_FILES_MAX = 20
RECENT_FILES_PATH = os.path.expanduser("~/.gemma-mcp-recent.json")
