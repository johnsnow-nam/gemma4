"""G-001 / G-002 / G-003 / G-004: Git 통합"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def _run_git(args: list[str], cwd: str | None = None, timeout: int = 5) -> tuple[str, str, int]:
    try:
        r = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or subprocess.os.getcwd(),  # type: ignore[attr-defined]
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1


def is_git_repo(cwd: str | None = None) -> bool:
    _, _, code = _run_git(["rev-parse", "--git-dir"], cwd=cwd)
    return code == 0


def get_branch(cwd: str | None = None) -> str:
    out, _, code = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return out if code == 0 else "-"


def get_status(cwd: str | None = None) -> str:
    """G-001: git status --short 결과"""
    out, _, code = _run_git(["status", "--short"], cwd=cwd)
    return out if code == 0 else ""


def get_status_summary(cwd: str | None = None) -> str:
    """변경 파일 목록 요약 (UI 표시용)"""
    status = get_status(cwd)
    if not status:
        return ""
    lines = status.strip().splitlines()
    summary_lines = []
    for line in lines[:10]:
        if len(line) >= 3:
            flag = line[:2].strip()
            fname = line[3:]
            summary_lines.append(f"  [{flag}] {fname}")
    if len(lines) > 10:
        summary_lines.append(f"  ... 외 {len(lines) - 10}개")
    return "\n".join(summary_lines)


def get_diff(staged_only: bool = False, cwd: str | None = None) -> str:
    """G-002: git diff 결과"""
    args = ["diff"]
    if staged_only:
        args.append("--staged")
    out, _, _ = _run_git(args, cwd=cwd, timeout=10)
    return out


def get_staged_diff(cwd: str | None = None) -> str:
    return get_diff(staged_only=True, cwd=cwd)


def git_add(path: str, cwd: str | None = None) -> tuple[bool, str]:
    out, err, code = _run_git(["add", path], cwd=cwd)
    return code == 0, err or out


def git_commit(message: str, cwd: str | None = None) -> tuple[bool, str]:
    out, err, code = _run_git(["commit", "-m", message], cwd=cwd)
    if code == 0:
        return True, out
    return False, err


def generate_commit_message_prompt(diff: str) -> str:
    """G-003: Conventional Commits 형식 메시지 생성용 프롬프트"""
    return (
        "다음 git diff를 분석하여 Conventional Commits 형식의 커밋 메시지를 생성해줘.\n"
        "형식: type(scope): description\n"
        "type 종류: feat, fix, docs, refactor, test, chore, style, perf\n"
        "규칙:\n"
        "- 제목은 50자 이내\n"
        "- 한국어로 작성\n"
        "- 본문 없이 제목만\n"
        "- 커밋 메시지만 출력 (설명 없이)\n\n"
        f"```diff\n{diff[:4000]}\n```"
    )


def get_vram_info() -> str:
    """U-003: nvidia-smi VRAM 정보"""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            if len(parts) >= 2:
                used = int(parts[0].strip())
                total = int(parts[1].strip())
                pct = used / total * 100
                return f"{used}/{total}MB ({pct:.0f}%)"
    except Exception:
        pass
    return "N/A"
