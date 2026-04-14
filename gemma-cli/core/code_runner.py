"""코드/셸 실행 — C-001, C-002, C-003"""
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

DANGEROUS_PATTERNS = ["rm -rf", "dd if=", "mkfs", "> /dev/", ":(){ :|:& };:"]
TIMEOUT_SECONDS = 30


def is_dangerous(cmd: str) -> bool:
    return any(pat in cmd for pat in DANGEROUS_PATTERNS)


def run_shell(cmd: str, cwd: str | None = None) -> tuple[str, str, float]:
    """
    셸 명령어 실행.
    반환: (stdout, stderr, elapsed_sec)
    """
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=cwd or os.getcwd(),
        )
        elapsed = time.time() - start
        return result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        return "", f"[타임아웃] {TIMEOUT_SECONDS}초 초과", time.time() - start
    except Exception as e:
        return "", str(e), time.time() - start


def run_file(file_path: str, cwd: str | None = None) -> tuple[str, str, float]:
    """
    C-001: 파일 실행 (Python, Bash, Node, C 자동 감지)
    반환: (stdout, stderr, elapsed_sec)
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".py":
        cmd = f"python3 {shlex.quote(str(p))}"
    elif ext in {".sh", ".bash"}:
        cmd = f"bash {shlex.quote(str(p))}"
    elif ext == ".js":
        cmd = f"node {shlex.quote(str(p))}"
    elif ext == ".c":
        bin_path = p.with_suffix("")
        compile_cmd = f"gcc {shlex.quote(str(p))} -o {shlex.quote(str(bin_path))}"
        out, err, t = run_shell(compile_cmd, cwd)
        if err and "error" in err.lower():
            return out, f"[컴파일 오류]\n{err}", t
        return run_shell(str(bin_path), cwd or str(p.parent))
    elif ext == ".cpp":
        bin_path = p.with_suffix("")
        compile_cmd = f"g++ {shlex.quote(str(p))} -o {shlex.quote(str(bin_path))}"
        out, err, t = run_shell(compile_cmd, cwd)
        if err and "error" in err.lower():
            return out, f"[컴파일 오류]\n{err}", t
        return run_shell(str(bin_path), cwd or str(p.parent))
    else:
        return "", f"[오류] 지원하지 않는 파일 형식: {ext}", 0.0

    return run_shell(cmd, cwd or str(p.parent))


def run_code_block(lang: str, code: str) -> tuple[str, str, float]:
    """
    C-002: AI 생성 코드를 임시파일에 저장 후 실행.
    반환: (stdout, stderr, elapsed_sec)
    """
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "bash": ".sh", "sh": ".sh",
        "c": ".c",
        "cpp": ".cpp", "c++": ".cpp",
    }
    ext = ext_map.get(lang.lower(), "")
    if not ext:
        return "", f"[오류] 실행 불가 언어: {lang}", 0.0

    tmp = tempfile.mktemp(suffix=ext)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(code)
        if ext == ".sh":
            os.chmod(tmp, 0o755)
        return run_file(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        # C/C++ 바이너리도 정리
        if ext in {".c", ".cpp"}:
            bin_path = tmp.replace(ext, "")
            try:
                os.unlink(bin_path)
            except OSError:
                pass


def is_runnable_lang(lang: str) -> bool:
    """실행 가능한 언어인지 확인"""
    runnable = {"python", "py", "javascript", "js", "bash", "sh", "c", "cpp", "c++"}
    return lang.lower() in runnable
