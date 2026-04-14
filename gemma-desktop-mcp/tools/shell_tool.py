"""T-006: 셸 명령어 실행 도구"""
from __future__ import annotations
import os
import subprocess
import time

from config.settings import DANGEROUS_SHELL_PATTERNS, BLOCKED_SHELL_PREFIXES, SHELL_TIMEOUT


def _is_dangerous(command: str) -> tuple[bool, str]:
    cmd_lower = command.lower().strip()
    for prefix in BLOCKED_SHELL_PREFIXES:
        if cmd_lower.startswith(prefix):
            return True, f"보안: '{prefix}' 명령어는 차단됩니다."
    for pattern in DANGEROUS_SHELL_PATTERNS:
        if pattern in command:
            return True, f"보안: 위험한 패턴 감지 — '{pattern}'"
    return False, ""


def run_shell(
    command: str,
    cwd: str | None = None,
    timeout: int = SHELL_TIMEOUT,
) -> str:
    """T-006: 셸 명령어 실행 후 결과 반환"""
    dangerous, reason = _is_dangerous(command)
    if dangerous:
        return f"[보안 차단] {reason}\n명령어: {command}"

    work_dir = os.path.expanduser(cwd) if cwd else os.getcwd()
    if not os.path.isdir(work_dir):
        return f"[오류] 디렉터리 없음: {cwd}"

    start = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        elapsed = time.time() - start

        parts = [f"$ {command}  ({elapsed:.2f}초, 종료코드: {result.returncode})"]
        if result.stdout:
            parts.append(f"stdout:\n{result.stdout.rstrip()}")
        if result.stderr:
            parts.append(f"stderr:\n{result.stderr.rstrip()}")
        if not result.stdout and not result.stderr:
            parts.append("(출력 없음)")

        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"[타임아웃] {timeout}초 초과: {command}"
    except Exception as e:
        return f"[오류] {e}"
