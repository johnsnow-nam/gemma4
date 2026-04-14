"""SHELL-001: 안전한 셸 명령어 실행"""
from __future__ import annotations
import asyncio
import os

from config.settings import BLOCKED_COMMANDS, SHELL_TIMEOUT


class ShellOps:
    async def run(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = SHELL_TIMEOUT,
    ) -> dict:
        """
        비동기 셸 실행.
        반환: {"returncode": int, "stdout": str, "stderr": str}
        """
        # 보안 검사
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"⛔ 차단된 명령어: {blocked}",
                }

        if command.strip().startswith("sudo "):
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "⛔ sudo 명령어는 허용되지 않습니다.",
            }

        work_dir = os.path.expanduser(cwd) if cwd else os.getcwd()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"⏱ 타임아웃 ({timeout}초 초과)",
                }

            return {
                "returncode": proc.returncode,
                "stdout": stdout_b.decode("utf-8", errors="replace"),
                "stderr": stderr_b.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    def format_result(self, result: dict, max_chars: int = 2000) -> str:
        """실행 결과를 텔레그램용 텍스트로 변환"""
        stdout = result["stdout"].strip()
        stderr = result["stderr"].strip()
        code = result["returncode"]

        parts = []
        if stdout:
            parts.append(f"```\n{stdout[-max_chars:]}\n```")
        if stderr:
            parts.append(f"stderr:\n```\n{stderr[-1000:]}\n```")
        if not stdout and not stderr:
            parts.append("_(출력 없음)_")

        icon = "✅" if code == 0 else "❌"
        header = f"{icon} 종료코드: {code}"
        return f"{header}\n" + "\n".join(parts)
