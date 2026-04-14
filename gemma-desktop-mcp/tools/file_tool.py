"""T-002, T-004: 파일 읽기/쓰기 도구"""
from __future__ import annotations
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import (
    HOME, ALLOWED_WRITE_PREFIXES, BLOCKED_WRITE_PREFIXES,
    MAX_FILE_SIZE_KB, RECENT_FILES_PATH, RECENT_FILES_MAX,
)

SOURCE_EXTS = {
    ".c", ".h", ".cpp", ".cxx", ".cc", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".sh", ".bash", ".md", ".txt", ".yaml",
    ".yml", ".json", ".toml", ".ini", ".cfg", ".html", ".css", ".sql", ".xml",
}


def _detect_encoding(path: Path) -> str:
    try:
        path.read_text(encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "euc-kr"


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def _track_recent(path: str) -> None:
    """최근 파일 목록 업데이트 (R-002)"""
    import json
    try:
        if os.path.exists(RECENT_FILES_PATH):
            data = json.loads(open(RECENT_FILES_PATH).read())
        else:
            data = []
        # 중복 제거 후 앞에 추가
        data = [p for p in data if p != path]
        data.insert(0, path)
        data = data[:RECENT_FILES_MAX]
        with open(RECENT_FILES_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def read_file_raw(path_str: str, encoding: str = "auto") -> tuple[str, str]:
    """파일 읽기. 반환: (content, error)"""
    path = Path(os.path.expanduser(path_str))
    if not path.exists():
        return "", f"파일 없음: {path}"
    if not path.is_file():
        return "", f"파일이 아닙니다: {path}"
    if _is_binary(path):
        return "", f"바이너리 파일: {path.name}"
    size_kb = path.stat().st_size / 1024
    if size_kb > MAX_FILE_SIZE_KB:
        # 큰 파일도 읽되 경고 포함
        pass
    enc = encoding if encoding != "auto" else _detect_encoding(path)
    try:
        content = path.read_text(encoding=enc, errors="replace")
        _track_recent(str(path))
        return content, ""
    except Exception as e:
        return "", str(e)


def read_file(path: str, encoding: str = "auto") -> str:
    """T-002: 파일 읽기 — MCP 도구용 (풍부한 메타정보 포함)"""
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return f"[오류] 파일 없음: {path}"
    if not p.is_file():
        return f"[오류] 파일이 아닙니다: {path}"
    if _is_binary(p):
        return f"[오류] 바이너리 파일은 읽을 수 없습니다: {p.name}"

    stat = p.stat()
    size_kb = stat.st_size / 1024
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

    warning = ""
    if size_kb > MAX_FILE_SIZE_KB:
        warning = f"\n[주의] 파일 크기가 큽니다: {size_kb:.0f} KB"

    enc = encoding if encoding != "auto" else _detect_encoding(p)
    try:
        content = p.read_text(encoding=enc, errors="replace")
        lines = content.count("\n") + 1
        _track_recent(str(p))
    except Exception as e:
        return f"[오류] 읽기 실패: {e}"

    # 언어 감지
    lang_map = {
        ".c": "c", ".h": "c", ".cpp": "cpp", ".py": "python", ".js": "javascript",
        ".ts": "typescript", ".go": "go", ".rs": "rust", ".sh": "bash",
        ".md": "markdown", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
        ".html": "html", ".css": "css", ".sql": "sql",
    }
    lang = lang_map.get(p.suffix.lower(), "")

    meta = f"파일: {p} | 크기: {size_kb:.1f} KB | 줄 수: {lines} | 수정: {mtime}{warning}"
    code_block = f"```{lang}\n{content}\n```" if lang else content

    return f"{meta}\n\n{code_block}"


def _is_write_allowed(path: str) -> tuple[bool, str]:
    """쓰기 경로 보안 검증"""
    abs_path = os.path.abspath(os.path.expanduser(path))
    for blocked in BLOCKED_WRITE_PREFIXES:
        if abs_path.startswith(blocked):
            return False, f"시스템 경로에는 쓸 수 없습니다: {blocked}"
    for allowed in ALLOWED_WRITE_PREFIXES:
        if abs_path.startswith(allowed):
            return True, ""
    return False, f"허용되지 않은 경로입니다. 홈 폴더({HOME}) 이하만 허용됩니다."


def write_file(
    path: str,
    content: str,
    backup: bool = True,
    mode: str = "write",
) -> str:
    """T-004: 파일 쓰기"""
    allowed, err = _is_write_allowed(path)
    if not allowed:
        return f"[보안 오류] {err}"

    p = Path(os.path.expanduser(path))
    backup_path = None

    if backup and p.exists():
        backup_path = p.with_suffix(p.suffix + ".bak")
        try:
            shutil.copy2(str(p), str(backup_path))
        except Exception as e:
            return f"[오류] 백업 실패: {e}"

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            with open(p, "a", encoding="utf-8") as f:
                f.write(content)
            action = "추가"
        else:
            p.write_text(content, encoding="utf-8")
            action = "저장"

        result = f"[완료] 파일 {action}: {p}"
        if backup_path:
            result += f"\n[백업] {backup_path}"
        return result
    except Exception as e:
        return f"[오류] 파일 쓰기 실패: {e}"


def get_recent_files() -> list[str]:
    """R-002: 최근 파일 목록"""
    import json
    try:
        if os.path.exists(RECENT_FILES_PATH):
            data = json.loads(open(RECENT_FILES_PATH).read())
            return [p for p in data if os.path.exists(p)]
    except Exception:
        pass
    return []
