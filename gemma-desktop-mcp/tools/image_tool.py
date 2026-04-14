"""T-005: 이미지 분석 도구"""
from __future__ import annotations
import base64
import os
from pathlib import Path

import ollama

from config.settings import OLLAMA_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE

_client = ollama.Client(host=OLLAMA_URL)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(
    path: str,
    prompt: str = "이 이미지를 상세히 분석해줘.",
    model: str = DEFAULT_MODEL,
) -> str:
    """T-005: 이미지 파일을 Gemma4 vision으로 분석"""
    p = Path(os.path.expanduser(path))

    if not p.exists():
        return f"[오류] 이미지 파일 없음: {path}"
    if p.suffix.lower() not in IMAGE_EXTS:
        return f"[오류] 지원하지 않는 이미지 형식: {p.suffix} (지원: {', '.join(IMAGE_EXTS)})"

    size_kb = p.stat().st_size / 1024
    meta = f"이미지: {p.name} ({size_kb:.0f} KB)"

    try:
        img_b64 = encode_image(str(p))
    except Exception as e:
        return f"[오류] 이미지 읽기 실패: {e}"

    try:
        resp = _client.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [img_b64],
            }],
            stream=False,
            options={"temperature": DEFAULT_TEMPERATURE},
        )
        return f"{meta}\n\n{resp.message.content}"
    except Exception as e:
        return f"[오류] Gemma4 vision 분석 실패: {e}"
