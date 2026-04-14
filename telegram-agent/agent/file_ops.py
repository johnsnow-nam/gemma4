"""FILE-001: 파일 읽기/쓰기/검색"""
from __future__ import annotations
import os
import shutil
from pathlib import Path

from config.settings import MAX_FILE_LINES, MAX_PROJECT_FILES

IGNORE_DIRS = {
    ".git", "build", "node_modules", ".cache", "__pycache__",
    ".venv", "venv", "dist", "out", "target", ".idea", "sdkconfig.old",
}
SOURCE_EXTS = {
    ".c", ".h", ".cpp", ".cxx", ".py", ".js", ".ts",
    ".md", ".yaml", ".yml", ".json", ".cmake", ".toml",
}


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def _read_file(path: str, max_lines: int = MAX_FILE_LINES) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            head = "".join(lines[:max_lines])
            return f"{head}\n... ({len(lines)}줄 중 {max_lines}줄 표시)"
        return "".join(lines)
    except Exception as e:
        return f"[읽기 실패: {e}]"


class FileOps:
    def find_and_read(self, project_path: str, filename: str) -> str:
        """파일명으로 프로젝트 내 탐색 후 읽기"""
        root = os.path.expanduser(project_path)
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            if filename in files:
                fp = os.path.join(dirpath, filename)
                content = _read_file(fp)
                rel = os.path.relpath(fp, root)
                return f"### {rel}\n```\n{content}\n```"
        return ""

    def find_file_path(self, project_path: str, filename: str) -> str | None:
        """파일 절대 경로 반환"""
        root = os.path.expanduser(project_path)
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            if filename in files:
                return os.path.join(dirpath, filename)
        return None

    def read_project_summary(self, project_path: str) -> str:
        """프로젝트 핵심 파일 요약 수집"""
        root = os.path.expanduser(project_path)
        collected: list[str] = []
        file_count = 0

        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in sorted(files):
                if file_count >= MAX_PROJECT_FILES:
                    break
                p = os.path.join(dirpath, fname)
                if Path(fname).suffix not in SOURCE_EXTS:
                    continue
                if _is_binary(p):
                    continue
                rel = os.path.relpath(p, root)
                content = _read_file(p, max_lines=80)
                collected.append(f"### {rel}\n```\n{content}\n```")
                file_count += 1

        if not collected:
            return f"[프로젝트 파일 없음: {project_path}]"
        return "\n\n".join(collected)

    def get_folder_tree(self, project_path: str, max_depth: int = 4) -> str:
        """폴더 트리 문자열 반환"""
        root = Path(os.path.expanduser(project_path))
        if not root.exists():
            return f"[경로 없음: {project_path}]"

        lines = [f"{root.name}/"]

        def _tree(path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            except PermissionError:
                return
            for i, entry in enumerate(entries):
                if entry.name in IGNORE_DIRS:
                    continue
                conn = "└── " if i == len(entries) - 1 else "├── "
                lines.append(f"{prefix}{conn}{entry.name}{'/' if entry.is_dir() else ''}")
                if entry.is_dir():
                    ext = "    " if i == len(entries) - 1 else "│   "
                    _tree(entry, prefix + ext, depth + 1)

        _tree(root, "", 0)
        return "\n".join(lines)

    def save_with_backup(self, project_path: str, filename: str, content: str) -> str:
        """파일 저장 (.bak 백업)"""
        filepath = self.find_file_path(project_path, filename)
        if not filepath:
            filepath = os.path.join(os.path.expanduser(project_path), filename)

        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def search(self, project_path: str, query: str, pattern: str = "*") -> str:
        """파일 내용 검색 (grep)"""
        import fnmatch
        root = os.path.expanduser(project_path)
        results: list[str] = []
        count = 0

        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in files:
                if not fnmatch.fnmatch(fname, pattern):
                    continue
                fp = os.path.join(dirpath, fname)
                if _is_binary(fp):
                    continue
                try:
                    lines = open(fp, encoding="utf-8", errors="replace").readlines()
                    hits = [(i + 1, l.rstrip()) for i, l in enumerate(lines)
                            if query.lower() in l.lower()]
                    if hits:
                        rel = os.path.relpath(fp, root)
                        results.append(f"**{rel}**")
                        for lineno, line in hits[:5]:
                            results.append(f"  L{lineno}: {line[:100]}")
                        count += len(hits)
                        if len(results) > 50:
                            break
                except Exception:
                    continue

        if not results:
            return f"'{query}' 검색 결과 없음"
        return f"검색: '{query}'  총 {count}개\n\n" + "\n".join(results)
