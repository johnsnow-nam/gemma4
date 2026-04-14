"""GIT-001: Git 작업"""
from __future__ import annotations
import os
import subprocess


def _run(args: list[str], cwd: str, timeout: int = 10) -> tuple[str, str, int]:
    try:
        r = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1


class GitOps:
    def is_repo(self, path: str) -> bool:
        root = os.path.expanduser(path)
        _, _, code = _run(["rev-parse", "--git-dir"], root)
        return code == 0

    def get_status(self, path: str) -> str:
        root = os.path.expanduser(path)
        branch, _, _ = _run(["rev-parse", "--abbrev-ref", "HEAD"], root)
        status, _, _ = _run(["status", "--short"], root)
        log, _, _ = _run(["log", "--oneline", "-3"], root)

        lines = [f"브랜치: {branch or '?'}"]
        if status:
            lines.append(f"변경:\n{status}")
        else:
            lines.append("변경사항 없음")
        if log:
            lines.append(f"최근 커밋:\n{log}")
        return "\n".join(lines)

    def get_diff(self, path: str, staged: bool = False) -> str:
        root = os.path.expanduser(path)
        args = ["diff", "--staged"] if staged else ["diff", "HEAD"]
        out, _, _ = _run(args, root, timeout=15)
        if not out:
            return "변경사항 없음"
        # 너무 길면 잘라냄
        if len(out) > 4000:
            out = out[:4000] + "\n\n... (이하 생략)"
        return out

    def add_all(self, path: str) -> bool:
        root = os.path.expanduser(path)
        _, _, code = _run(["add", "-A"], root)
        return code == 0

    def commit(self, path: str, message: str) -> tuple[bool, str]:
        root = os.path.expanduser(path)
        self.add_all(root)
        out, err, code = _run(["commit", "-m", message], root)
        if code == 0:
            return True, out
        return False, err

    def get_log(self, path: str, n: int = 5) -> str:
        root = os.path.expanduser(path)
        out, _, _ = _run(["log", "--oneline", f"-{n}"], root)
        return out or "커밋 없음"
