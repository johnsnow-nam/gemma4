"""API-002: 서비스 상태 모니터"""
from __future__ import annotations
import subprocess
import requests


SERVICES: dict = {
    "ollama": {
        "label": "Ollama",
        "type": "http",
        "url": "http://localhost:11434",
        "systemd": "ollama",
        "icon": "AI",
    },
    "open-webui": {
        "label": "Open WebUI",
        "type": "http",
        "url": "http://localhost:8080",
        "systemd": "open-webui",
        "icon": "WEB",
    },
    "telegram-bot": {
        "label": "Telegram Bot",
        "type": "systemd",
        "systemd": "telegram-agent",
        "icon": "BOT",
    },
}


class ServiceMonitor:
    def get_all(self) -> dict:
        result = {}
        for key, cfg in SERVICES.items():
            result[key] = self._check(key, cfg)
        result["models"] = self._check_ollama_models()
        return result

    def _check(self, key: str, cfg: dict) -> dict:
        status = "stopped"

        # HTTP 체크
        if cfg["type"] == "http":
            try:
                r = requests.get(cfg["url"], timeout=2)
                status = "running" if r.status_code < 500 else "error"
            except Exception:
                status = "stopped"

        # systemd 보조 체크 (HTTP 실패 시 systemd로 재확인)
        systemd = cfg.get("systemd", "")
        if systemd:
            try:
                r = subprocess.run(
                    ["systemctl", "is-active", systemd],
                    capture_output=True, text=True, timeout=3,
                )
                sd_status = r.stdout.strip()
                if cfg["type"] == "systemd":
                    # systemd 전용 서비스
                    status = "running" if sd_status == "active" else (
                        "error" if sd_status == "failed" else "stopped"
                    )
                elif sd_status == "failed":
                    status = "error"
            except Exception:
                pass

        return {
            "label": cfg["label"],
            "status": status,
            "icon": cfg.get("icon", "SVC"),
            "uptime": self._get_uptime(systemd),
            "systemd": systemd,
        }

    def _check_ollama_models(self) -> list:
        try:
            r = requests.get("http://localhost:11434/api/ps", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                        "vram_gb": round(m.get("size_vram", 0) / 1e9, 1),
                        "status": "loaded",
                    }
                    for m in models
                ]
        except Exception:
            pass
        return []

    def _get_uptime(self, service_name: str) -> str:
        if not service_name:
            return ""
        try:
            r = subprocess.run(
                ["systemctl", "show", service_name,
                 "--property=ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=3,
            )
            ts = r.stdout.strip().replace("ActiveEnterTimestamp=", "").strip()
            if not ts or ts == "n/a":
                return ""
            # 간단히 날짜 부분만 반환
            parts = ts.split(" ")
            return " ".join(parts[1:3]) if len(parts) >= 3 else ts
        except Exception:
            return ""
