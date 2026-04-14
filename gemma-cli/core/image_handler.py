"""이미지 처리 — I-001, I-002, I-003, I-004"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MAX_IMAGES = 4


def validate_images(paths: list[str]) -> tuple[list[str], list[str]]:
    """
    이미지 경로 유효성 검사.
    반환: (유효_경로_목록, 오류_목록)
    """
    valid: list[str] = []
    errors: list[str] = []

    for raw in paths[:MAX_IMAGES]:
        p = Path(os.path.expanduser(raw))
        if not p.exists():
            errors.append(f"이미지 파일을 찾을 수 없습니다: {raw}")
            continue
        if p.suffix.lower() not in IMAGE_EXTS:
            errors.append(f"지원하지 않는 이미지 형식: {p.suffix}")
            continue
        valid.append(str(p))

    if len(paths) > MAX_IMAGES:
        errors.append(f"최대 {MAX_IMAGES}장까지 지원합니다. 처음 {MAX_IMAGES}장만 처리합니다.")

    return valid, errors


def image_meta_text(paths: list[str]) -> str:
    """이미지 메타정보 문자열 생성"""
    lines = []
    for i, p in enumerate(paths, 1):
        path = Path(p)
        size_kb = path.stat().st_size / 1024
        label = f"이미지 {i}"
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
            lines.append(f"[dim][{label}] {path.name} ({w}x{h}px, {size_kb:.0f} KB)[/dim]")
        except ImportError:
            lines.append(f"[dim][{label}] {path.name} ({size_kb:.0f} KB)[/dim]")
        except Exception:
            lines.append(f"[dim][{label}] {path.name} ({size_kb:.0f} KB)[/dim]")
    return "\n".join(lines)


def get_clipboard_image() -> str | None:
    """
    I-003: 클립보드에서 이미지를 임시파일로 저장.
    반환: 임시파일 경로 또는 None
    """
    tmp = tempfile.mktemp(suffix=".png")

    # xclip 시도
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
            capture_output=True, timeout=3
        )
        if r.returncode == 0 and r.stdout:
            with open(tmp, "wb") as f:
                f.write(r.stdout)
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # xsel 시도
    try:
        r = subprocess.run(
            ["xsel", "--clipboard", "--output"],
            capture_output=True, timeout=3
        )
        if r.returncode == 0 and r.stdout and r.stdout[:4] == b"\x89PNG":
            with open(tmp, "wb") as f:
                f.write(r.stdout)
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # wl-paste 시도 (Wayland)
    try:
        r = subprocess.run(
            ["wl-paste", "--type", "image/png"],
            capture_output=True, timeout=3
        )
        if r.returncode == 0 and r.stdout:
            with open(tmp, "wb") as f:
                f.write(r.stdout)
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return None


def take_screenshot() -> str | None:
    """
    I-004: 스크린샷 촬영 후 임시파일 저장.
    반환: 임시파일 경로 또는 None
    """
    tmp = tempfile.mktemp(suffix=".png")

    # scrot 시도
    try:
        r = subprocess.run(["scrot", tmp], capture_output=True, timeout=10)
        if r.returncode == 0 and Path(tmp).exists():
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # gnome-screenshot 시도
    try:
        r = subprocess.run(
            ["gnome-screenshot", "-f", tmp],
            capture_output=True, timeout=10
        )
        if r.returncode == 0 and Path(tmp).exists():
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # import (ImageMagick) 시도
    try:
        r = subprocess.run(
            ["import", "-window", "root", tmp],
            capture_output=True, timeout=10
        )
        if r.returncode == 0 and Path(tmp).exists():
            return tmp
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return None
