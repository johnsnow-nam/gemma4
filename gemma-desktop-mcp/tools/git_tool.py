"""T-007, T-008: Git 연동 도구"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


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


def _resolve_repo(path: str) -> str | None:
    p = os.path.expanduser(path)
    if not os.path.isdir(p):
        return None
    out, _, code = _run(["rev-parse", "--show-toplevel"], cwd=p)
    return out if code == 0 else None


def git_status(path: str = ".") -> str:
    """T-007: Git 저장소 상태 확인"""
    repo = _resolve_repo(path)
    if not repo:
        return f"[오류] Git 저장소가 아닙니다: {path}"

    branch, _, _ = _run(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    status_out, _, _ = _run(["status", "--short"], repo)
    staged_out, _, _ = _run(["diff", "--staged", "--name-only"], repo)
    log_out, _, _ = _run(["log", "--oneline", "-5"], repo)

    result = [f"## Git 상태: {repo}"]
    result.append(f"브랜치: **{branch}**")

    if status_out:
        result.append("\n변경된 파일:")
        for line in status_out.splitlines():
            flag = line[:2].strip()
            fname = line[3:].strip()
            result.append(f"  [{flag}] {fname}")
    else:
        result.append("\n변경된 파일: 없음")

    if staged_out:
        result.append("\nStaged 파일:")
        for f in staged_out.splitlines():
            result.append(f"  ✔ {f}")

    if log_out:
        result.append("\n최근 커밋:")
        for line in log_out.splitlines():
            result.append(f"  {line}")

    return "\n".join(result)


def git_diff(path: str = ".", staged: bool = False) -> str:
    """T-008: Git Diff 가져오기"""
    repo = _resolve_repo(path)
    if not repo:
        return f"[오류] Git 저장소가 아닙니다: {path}"

    args = ["diff"]
    if staged:
        args.append("--staged")
    out, err, code = _run(args, repo, timeout=15)

    if not out:
        label = "staged " if staged else ""
        return f"[{label}변경사항 없음]"

    # 길이 제한
    MAX_DIFF = 8000
    if len(out) > MAX_DIFF:
        out = out[:MAX_DIFF] + f"\n\n[... 너무 길어서 {len(out) - MAX_DIFF}자 잘림]"

    return f"```diff\n{out}\n```"
