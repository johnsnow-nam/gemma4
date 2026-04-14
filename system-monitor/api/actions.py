"""API-005: 서비스 시작/중지/재시작 + 로그"""
from __future__ import annotations
import subprocess

SYSTEMD_MAP = {
    "ollama": "ollama",
    "open-webui": "open-webui",
    "telegram-bot": "telegram-agent",
}


class ServiceActions:
    def _run(self, action: str, name: str) -> dict:
        service = SYSTEMD_MAP.get(name)
        if not service:
            return {"success": False, "message": f"알 수 없는 서비스: {name}"}
        try:
            r = subprocess.run(
                ["sudo", "systemctl", action, service],
                capture_output=True, text=True, timeout=15,
            )
            return {
                "success": r.returncode == 0,
                "message": (r.stdout or r.stderr or "OK").strip(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def start(self, name: str) -> dict:
        return self._run("start", name)

    def stop(self, name: str) -> dict:
        return self._run("stop", name)

    def restart(self, name: str) -> dict:
        return self._run("restart", name)

    def get_logs(self, name: str, lines: int = 50) -> str:
        service = SYSTEMD_MAP.get(name, name)
        try:
            r = subprocess.run(
                ["journalctl", "-u", service, f"-n{lines}",
                 "--no-pager", "--output=short-iso"],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout or "(로그 없음)"
        except Exception as e:
            return f"로그 조회 실패: {e}"
