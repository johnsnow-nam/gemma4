"""T-003: 폴더 탐색 도구"""
from __future__ import annotations
import os
from pathlib import Path

from config.settings import MAX_FOLDER_FILES

EXCLUDE_DIRS = {
    "node_modules", ".git", "build", "dist", "__pycache__",
    ".venv", "venv", "env", "target", ".cache", "out", "output",
    "bin", "obj", ".idea", ".vscode", ".next", ".nuxt",
}

SOURCE_EXTS = {
    ".c", ".h", ".cpp", ".cxx", ".cc", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".sh", ".bash", ".md", ".txt", ".yaml",
    ".yml", ".json", ".toml", ".ini", ".cfg", ".html", ".css", ".sql", ".xml",
    ".cmake",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

DEFAULT_PATTERNS = "**/*.c,**/*.h,**/*.py,**/*.js,**/*.ts,**/*.md,**/*.yaml,**/*.json"


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


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
        lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
        if entry.is_dir():
            ext = "    " if i == len(entries) - 1 else "│   "
            lines.extend(_build_tree(entry, prefix + ext, depth + 1, max_depth))
    return lines


def _match_patterns(path: Path, patterns: list[str]) -> bool:
    from fnmatch import fnmatch
    name = path.name
    suffix = path.suffix.lower()
    for pat in patterns:
        pat = pat.strip()
        if fnmatch(name, pat.split("/")[-1]):
            return True
        if pat.startswith("**") and fnmatch(name, pat.lstrip("*/").lstrip("*")):
            return True
    return False


def read_folder(
    path: str,
    pattern: str = DEFAULT_PATTERNS,
    max_files: int = MAX_FOLDER_FILES,
    include_content: bool = True,
) -> str:
    """T-003: 폴더 탐색 및 파일 수집"""
    root = Path(os.path.expanduser(path.rstrip("/")))

    if not root.exists():
        return f"[오류] 폴더 없음: {path}"
    if not root.is_dir():
        return f"[오류] 폴더가 아닙니다: {path}"

    # 폴더 트리
    tree_lines = [f"{root.name}/"] + _build_tree(root)
    tree_str = "\n".join(tree_lines)

    # 파일 수집
    patterns = pattern.split(",") if pattern else []
    collected: list[Path] = []

    for p in sorted(root.rglob("*")):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in IMAGE_EXTS:
            continue
        if _is_binary(p):
            continue
        if patterns:
            if not _match_patterns(p, patterns):
                # 패턴 없어도 소스파일 포함
                if p.suffix.lower() not in SOURCE_EXTS:
                    continue
        collected.append(p)

    total = len(collected)
    if total > max_files:
        collected = collected[:max_files]
        truncated = f"\n[주의] {total}개 파일 중 {max_files}개만 포함됩니다."
    else:
        truncated = ""

    result = [f"## 폴더: {root}\n\n```\n{tree_str}\n```{truncated}"]

    if include_content:
        from tools.file_tool import read_file_raw
        for p in collected:
            content, err = read_file_raw(str(p))
            if err:
                result.append(f"### {p.relative_to(root)}\n[오류] {err}")
            else:
                lang_map = {
                    ".c": "c", ".h": "c", ".cpp": "cpp", ".py": "python",
                    ".js": "javascript", ".ts": "typescript", ".go": "go",
                    ".rs": "rust", ".sh": "bash", ".md": "markdown",
                    ".yaml": "yaml", ".yml": "yaml", ".json": "json",
                }
                lang = lang_map.get(p.suffix.lower(), "")
                block = f"```{lang}\n{content}\n```"
                result.append(f"### {p.relative_to(root)}\n{block}")
    else:
        result.append(
            "파일 목록:\n" + "\n".join(f"  - {p.relative_to(root)}" for p in collected)
        )

    return "\n\n---\n\n".join(result)
