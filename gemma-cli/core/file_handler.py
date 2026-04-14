"""파일/폴더 처리 — F-001, F-002, F-003, F-004, F-006"""
from __future__ import annotations

import os
import re
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Optional

# 지원 소스 파일 확장자
SOURCE_EXTS = {
    ".c", ".h", ".cpp", ".cxx", ".cc",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt",
    ".sh", ".bash", ".zsh",
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss",
    ".sql", ".xml",
    ".cmake", "Makefile", "Kconfig",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

# 자동 제외 폴더
EXCLUDE_DIRS = {
    "node_modules", ".git", "build", "dist", "__pycache__",
    ".venv", "venv", "env", ".env", "target", ".cache",
    "out", "output", "bin", "obj", ".idea", ".vscode",
}

MAX_FILE_SIZE_KB = 500
MAX_GLOB_FILES = 30
MAX_FOLDER_FILES = 50


def _detect_encoding(path: Path) -> str:
    """UTF-8 / EUC-KR 인코딩 자동 감지"""
    try:
        path.read_text(encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "euc-kr"


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _file_meta(path: Path) -> str:
    stat = path.stat()
    size_kb = stat.st_size / 1024
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    try:
        lines = path.read_text(encoding=_detect_encoding(path)).count("\n")
    except Exception:
        lines = "?"
    return f"크기: {size_kb:.1f} KB | 수정: {mtime} | 줄 수: {lines}"


def _lang_from_ext(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".c": "c", ".h": "c", ".cpp": "cpp", ".cxx": "cpp",
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
        ".sh": "bash", ".bash": "bash",
        ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".toml": "toml", ".sql": "sql",
        ".html": "html", ".css": "css",
    }
    return mapping.get(suffix, "")


def read_single_file(path_str: str) -> tuple[str, list[str]]:
    """
    단일 파일 읽기 (F-001)
    반환: (context_text, warnings)
    """
    path = Path(os.path.expanduser(path_str))
    warnings: list[str] = []

    if not path.exists():
        return f"[오류] 파일을 찾을 수 없습니다: {path}", ["파일 없음"]

    if path.suffix.lower() in IMAGE_EXTS:
        return "", []  # 이미지는 image_handler에서 처리

    if _is_binary(path):
        return f"[경고] 바이너리 파일이라 읽을 수 없습니다: {path.name}", ["바이너리"]

    size_kb = path.stat().st_size / 1024
    if size_kb > MAX_FILE_SIZE_KB:
        warnings.append(f"파일이 큽니다: {size_kb:.0f} KB (>{MAX_FILE_SIZE_KB} KB)")

    try:
        enc = _detect_encoding(path)
        content = path.read_text(encoding=enc)
    except Exception as e:
        return f"[오류] 파일 읽기 실패: {e}", ["읽기 실패"]

    lang = _lang_from_ext(path)
    meta = _file_meta(path)
    block = f"```{lang}\n{content}\n```" if lang else content

    result = f"### 파일: {path}\n_{meta}_\n\n{block}"
    return result, warnings


def read_glob_pattern(pattern: str, base_dir: str = ".") -> tuple[str, list[str]]:
    """
    Glob 패턴 파일 읽기 (F-003)
    """
    base = Path(os.path.expanduser(base_dir))
    warnings: list[str] = []

    # Path.glob 사용
    matches = sorted(base.glob(pattern))
    matches = [p for p in matches if p.is_file() and not _is_binary(p)]
    matches = [p for p in matches if p.suffix.lower() not in IMAGE_EXTS]

    if not matches:
        return f"[경고] 패턴에 일치하는 파일이 없습니다: {pattern}", ["파일 없음"]

    if len(matches) > MAX_GLOB_FILES:
        warnings.append(
            f"패턴에 {len(matches)}개 파일이 일치합니다. 처음 {MAX_GLOB_FILES}개만 읽습니다."
        )
        matches = matches[:MAX_GLOB_FILES]

    parts = [f"## Glob 패턴: `{pattern}` — {len(matches)}개 파일\n"]
    for p in matches:
        text, w = read_single_file(str(p))
        warnings.extend(w)
        parts.append(text)

    return "\n\n---\n\n".join(parts), warnings


def _build_tree(root: Path, prefix: str = "", depth: int = 0, max_depth: int = 4) -> list[str]:
    if depth > max_depth:
        return []
    lines = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return []
    for i, entry in enumerate(entries):
        if entry.name in EXCLUDE_DIRS:
            continue
        connector = "└── " if i == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            lines.extend(_build_tree(entry, prefix + extension, depth + 1, max_depth))
    return lines


def read_folder(folder_str: str) -> tuple[str, list[str]]:
    """
    폴더 전체 읽기 (F-004)
    """
    root = Path(os.path.expanduser(folder_str.rstrip("/")))
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        return f"[오류] 폴더를 찾을 수 없습니다: {root}", ["폴더 없음"]

    # 폴더 트리
    tree_lines = [f"{root.name}/"] + _build_tree(root)
    tree_str = "\n".join(tree_lines)

    # 소스파일 수집
    collected: list[Path] = []
    for p in sorted(root.rglob("*")):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        if _is_binary(p):
            continue
        if p.suffix.lower() in IMAGE_EXTS:
            continue
        if p.suffix.lower() in SOURCE_EXTS or p.name in SOURCE_EXTS:
            collected.append(p)

    if len(collected) > MAX_FOLDER_FILES:
        warnings.append(
            f"폴더에 {len(collected)}개 파일이 있습니다. 처음 {MAX_FOLDER_FILES}개만 읽습니다."
        )
        collected = collected[:MAX_FOLDER_FILES]

    parts = [f"## 폴더: {root}\n\n```\n{tree_str}\n```"]
    for p in collected:
        text, w = read_single_file(str(p))
        warnings.extend(w)
        parts.append(text)

    return "\n\n---\n\n".join(parts), warnings


def is_image(path_str: str) -> bool:
    return Path(path_str).suffix.lower() in IMAGE_EXTS


def parse_at_references(user_input: str) -> tuple[str, list[str], list[str]]:
    """
    사용자 입력에서 @참조를 파싱.
    반환: (깨끗한_프롬프트, 파일_경로_목록, 이미지_경로_목록)
    """
    tokens = user_input.split()
    file_refs: list[str] = []
    image_refs: list[str] = []
    clean_tokens: list[str] = []

    for token in tokens:
        if token.startswith("@"):
            ref = token[1:]
            if is_image(ref):
                image_refs.append(ref)
            else:
                file_refs.append(ref)
        else:
            clean_tokens.append(token)

    clean_prompt = " ".join(clean_tokens)
    return clean_prompt, file_refs, image_refs


# ---------------------------------------------------------------------------
# F-006: 코드블록 추출 및 파일 쓰기
# ---------------------------------------------------------------------------

def extract_code_blocks(text: str) -> list[dict]:
    """
    AI 응답에서 코드블록 추출.
    반환: [{"lang": str, "code": str, "suggested_filename": str}]
    """
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    blocks = []
    for m in pattern.finditer(text):
        lang = m.group(1).strip()
        code = m.group(2)
        suggested = _suggest_filename(lang, code)
        blocks.append({"lang": lang, "code": code, "suggested_filename": suggested})
    return blocks


def _suggest_filename(lang: str, code: str) -> str:
    """언어 + 코드 내용에서 파일명 추천"""
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "bash": ".sh", "sh": ".sh",
        "c": ".c",
        "cpp": ".cpp", "c++": ".cpp",
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
        "html": ".html",
        "css": ".css",
        "json": ".json",
        "yaml": ".yaml", "yml": ".yaml",
        "toml": ".toml",
        "sql": ".sql",
        "markdown": ".md", "md": ".md",
    }
    ext = ext_map.get(lang.lower(), ".txt")

    # 코드에서 파일명 힌트 추출
    lines = code.strip().splitlines()
    for line in lines[:5]:
        # Python: def main() → main.py
        if ext == ".py":
            m = re.search(r"^class\s+(\w+)|^def\s+(\w+)", line)
            if m:
                name = (m.group(1) or m.group(2)).lower()
                return f"{name}{ext}"
        # Java: class Foo
        if ext == ".java":
            m = re.search(r"^public\s+class\s+(\w+)", line)
            if m:
                return f"{m.group(1)}{ext}"

    return f"output{ext}"


def _make_diff(old_content: str, new_content: str, filename: str) -> str:
    """간단한 unified diff 생성"""
    import difflib
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    return "".join(diff)


def write_file_with_backup(file_path: str, content: str) -> tuple[bool, str]:
    """
    F-006: .bak 백업 후 파일 쓰기.
    반환: (성공, 메시지)
    """
    path = Path(file_path)
    backup_path = None

    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(str(path), str(backup_path))
        except Exception as e:
            return False, f"백업 실패: {e}"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        msg = f"파일 저장: {path}"
        if backup_path:
            msg += f" (백업: {backup_path})"
        return True, msg
    except Exception as e:
        return False, f"파일 쓰기 실패: {e}"


def get_file_diff_preview(file_path: str, new_content: str) -> str:
    """기존 파일과 새 내용의 diff 미리보기"""
    path = Path(file_path)
    if not path.exists():
        return f"[새 파일] {file_path}"
    try:
        old = path.read_text(encoding="utf-8")
    except Exception:
        return "[기존 파일 읽기 실패]"
    return _make_diff(old, new_content, path.name)
