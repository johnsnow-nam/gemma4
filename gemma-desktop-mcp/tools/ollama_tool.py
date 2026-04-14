"""T-001, T-012: Gemma4 추론 도구"""
from __future__ import annotations
import base64
import os
from pathlib import Path

import ollama

from config.settings import OLLAMA_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE

_client = ollama.Client(host=OLLAMA_URL)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def ask_gemma(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    system: str = "",
) -> str:
    """T-001: 로컬 Gemma4 모델에게 질문 (비스트리밍)"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _client.chat(
        model=model,
        messages=messages,
        stream=False,
        options={"temperature": temperature},
    )
    return resp.message.content


def ask_gemma_with_files(
    file_paths: list[str],
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """T-012: 파일 내용과 함께 Gemma4에게 질문 (복합 도구)"""
    from tools.file_tool import read_file_raw
    from tools.image_tool import encode_image

    context_parts: list[str] = []
    image_paths: list[str] = []
    errors: list[str] = []

    for path_str in file_paths:
        path = Path(os.path.expanduser(path_str))
        if not path.exists():
            errors.append(f"파일 없음: {path_str}")
            continue
        if path.suffix.lower() in IMAGE_EXTS:
            image_paths.append(str(path))
        else:
            content, err = read_file_raw(str(path))
            if err:
                errors.append(err)
            else:
                context_parts.append(f"### 파일: {path}\n```\n{content}\n```")

    error_str = "\n".join(errors) + "\n" if errors else ""
    context_str = "\n\n".join(context_parts)
    full_prompt = f"{error_str}{context_str}\n\n---\n\n{prompt}" if context_str else prompt

    messages = [{"role": "user", "content": full_prompt}]

    if image_paths:
        images_b64 = [encode_image(p) for p in image_paths]
        messages[-1]["images"] = images_b64

    resp = _client.chat(
        model=model,
        messages=messages,
        stream=False,
        options={"temperature": temperature},
    )
    return resp.message.content


def list_ollama_models() -> list[dict]:
    """T-011: Ollama 모델 목록 반환"""
    try:
        resp = _client.list()
        return resp.get("models", [])
    except Exception as e:
        return [{"error": str(e)}]
