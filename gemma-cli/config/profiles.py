"""P-001 / P-002 / P-003: 프로파일 시스템"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROFILES_DIR = Path.home() / ".gemma-cli" / "profiles"

# P-003 내장 프로파일
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "esp32": {
        "name": "esp32",
        "description": "ESP32 임베디드 개발",
        "system_prompt": (
            "당신은 ESP32 임베디드 개발 전문가입니다. "
            "FreeRTOS, ESP-IDF, Arduino 프레임워크에 능통합니다. "
            "C/C++ 코드를 중심으로 도움을 드리며, 하드웨어 제약사항을 항상 고려합니다. "
            "한국어로 대화합니다."
        ),
        "model": "gemma4:26b",
        "file_patterns": ["*.c", "*.h", "*.cpp", "*.ino", "CMakeLists.txt", "sdkconfig"],
        "root_path": None,
    },
    "ocpp": {
        "name": "ocpp",
        "description": "OCPP 전기차 충전 프로토콜",
        "system_prompt": (
            "당신은 OCPP (Open Charge Point Protocol) 전문가입니다. "
            "OCPP 1.6J, 2.0.1 스펙을 잘 알고 있으며, 충전소 관리 시스템(CSMS)과 "
            "충전기(CP) 간의 통신 프로토콜 구현에 전문성이 있습니다. "
            "WebSocket, JSON 기반 메시지 처리, 상태 머신 구현을 도와드립니다. "
            "한국어로 대화합니다."
        ),
        "model": "gemma4:26b",
        "file_patterns": ["*.py", "*.js", "*.ts", "*.json"],
        "root_path": None,
    },
    "general": {
        "name": "general",
        "description": "일반 개발 도우미",
        "system_prompt": (
            "당신은 gemma-cli 로컬 AI 어시스턴트입니다. "
            "사용자의 코드, 파일, 프로젝트를 분석하고 도움을 드립니다. "
            "한국어로 대화하며, 코드는 항상 마크다운 코드블록으로 작성합니다. "
            "파일 내용이 제공되면 그것을 기반으로 정확한 분석을 합니다."
        ),
        "model": "gemma4:26b",
        "file_patterns": [],
        "root_path": None,
    },
    "korean": {
        "name": "korean",
        "description": "한국어 특화 도우미",
        "system_prompt": (
            "당신은 한국어 특화 AI 어시스턴트입니다. "
            "모든 응답을 자연스러운 한국어로 작성합니다. "
            "기술 문서, 코드 설명, 번역 등 다양한 작업을 한국어로 도와드립니다. "
            "코드 예시가 필요할 때는 마크다운 코드블록을 사용합니다."
        ),
        "model": "gemma4:e4b",
        "file_patterns": ["*.md", "*.txt"],
        "root_path": None,
    },
}


def list_profiles() -> list[str]:
    """내장 + 사용자 프로파일 이름 목록"""
    names = list(BUILTIN_PROFILES.keys())
    if PROFILES_DIR.exists():
        for p in sorted(PROFILES_DIR.glob("*.json")):
            name = p.stem
            if name not in names:
                names.append(name)
    return names


def get_profile(name: str) -> dict[str, Any] | None:
    """이름으로 프로파일 로드"""
    if name in BUILTIN_PROFILES:
        return dict(BUILTIN_PROFILES[name])
    path = PROFILES_DIR / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def create_profile(name: str, data: dict[str, Any]) -> Path:
    """P-001: 새 프로파일 생성"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    data["name"] = name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def detect_local_profile() -> str | None:
    """P-002: 현재 디렉터리에서 .gemma-cli 파일 감지"""
    cwd = Path.cwd()
    for directory in [cwd] + list(cwd.parents):
        marker = directory / ".gemma-cli"
        if marker.exists() and marker.is_file():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                return data.get("profile")
            except Exception:
                pass
    return None


def format_profile_info(profile: dict[str, Any]) -> str:
    lines = [
        f"[bold]프로파일: [cyan]{profile.get('name', '?')}[/cyan][/bold]",
        f"  설명: {profile.get('description', '-')}",
        f"  모델: {profile.get('model', '-')}",
        f"  파일 패턴: {', '.join(profile.get('file_patterns', [])) or '-'}",
        f"  루트 경로: {profile.get('root_path') or '현재 디렉터리'}",
    ]
    return "\n".join(lines)
