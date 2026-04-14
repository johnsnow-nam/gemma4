"""M-003: 자동 모델 라우팅"""
from __future__ import annotations

from config.settings import get_settings

MODEL_26B = "gemma4:26b"
MODEL_E4B = "gemma4:e4b"


def select_model(base_model: str, message: str, has_images: bool, client) -> str:
    """메시지·이미지 기반 자동 모델 선택"""
    settings = get_settings()
    if not settings.auto_routing:
        return base_model

    if has_images:
        target = MODEL_26B
    elif len(message) > 2000:
        target = MODEL_26B
    else:
        if client.is_model_available(MODEL_E4B):
            target = MODEL_E4B
        else:
            target = base_model

    return target
