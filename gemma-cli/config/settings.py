"""S-001 / S-002: ~/.gemma-cli/config.yaml 읽기/쓰기"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

CONFIG_DIR = Path.home() / ".gemma-cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULTS: dict[str, Any] = {
    "model": "gemma4:26b",
    "ollama_url": "http://localhost:11434",
    "temperature": 0.3,
    "num_ctx": 8192,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "auto_routing": True,
    "git_status_on_start": True,
    "context_warn_yellow": 0.80,
    "context_warn_red": 0.95,
    "verbose": False,
}


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        return {}
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        # Fallback: write as key: value lines
        with open(path, "w", encoding="utf-8") as f:
            for k, v in data.items():
                f.write(f"{k}: {v!r}\n")
        return
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


class Settings:
    """config.yaml 기반 설정 관리"""

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._data.update(_load_yaml(CONFIG_FILE))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def reset(self, key: str | None = None) -> None:
        if key:
            self._data[key] = DEFAULTS.get(key)
        else:
            self._data = dict(DEFAULTS)
        self._save()

    def _save(self) -> None:
        _save_yaml(CONFIG_FILE, self._data)

    def show(self) -> str:
        lines = ["[bold]현재 설정:[/bold]"]
        for k, v in sorted(self._data.items()):
            default_mark = " [dim](기본값)[/dim]" if v == DEFAULTS.get(k) else ""
            lines.append(f"  [cyan]{k}[/cyan] = [yellow]{v!r}[/yellow]{default_mark}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return dict(self._data)

    # 편의 프로퍼티
    @property
    def model(self) -> str:
        return self.get("model", DEFAULTS["model"])

    @property
    def ollama_url(self) -> str:
        return self.get("ollama_url", DEFAULTS["ollama_url"])

    @property
    def temperature(self) -> float:
        return float(self.get("temperature", DEFAULTS["temperature"]))

    @property
    def num_ctx(self) -> int:
        return int(self.get("num_ctx", DEFAULTS["num_ctx"]))

    @property
    def top_p(self) -> float:
        return float(self.get("top_p", DEFAULTS["top_p"]))

    @property
    def repeat_penalty(self) -> float:
        return float(self.get("repeat_penalty", DEFAULTS["repeat_penalty"]))

    @property
    def auto_routing(self) -> bool:
        return bool(self.get("auto_routing", DEFAULTS["auto_routing"]))

    @property
    def verbose(self) -> bool:
        return bool(self.get("verbose", DEFAULTS["verbose"]))


# 전역 싱글톤
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
