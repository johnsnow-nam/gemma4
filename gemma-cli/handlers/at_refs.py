"""@ 파일 참조 처리 — 파일·글로브·폴더·이미지"""
from __future__ import annotations

import os

from rich.console import Console

from core.file_handler import (
    read_single_file, read_glob_pattern, read_folder,
)
from core.image_handler import validate_images

console = Console()


def process_at_references(
    file_refs: list[str],
    image_refs: list[str],
    client,
    verbose: bool = False,
) -> tuple[str, list[str]]:
    """파일 참조를 읽어 (context_text, valid_image_paths) 반환"""
    context_parts: list[str] = []
    all_warnings: list[str] = []

    for ref in file_refs:
        ref_exp = os.path.expanduser(ref)
        if "*" in ref or "?" in ref:
            if verbose:
                console.print(f"[dim]Glob 패턴 읽기: {ref}[/dim]")
            text, warns = read_glob_pattern(ref)
            context_parts.append(text)
            all_warnings.extend(warns)
        elif os.path.isdir(ref_exp) or ref.endswith("/"):
            if verbose:
                console.print(f"[dim]폴더 읽기: {ref}[/dim]")
            text, warns = read_folder(ref)
            context_parts.append(text)
            all_warnings.extend(warns)
        else:
            if verbose:
                console.print(f"[dim]파일 읽기: {ref}[/dim]")
            text, warns = read_single_file(ref)
            context_parts.append(text)
            all_warnings.extend(warns)

    valid_images: list[str] = []
    if image_refs:
        valid_images, img_errors = validate_images(image_refs)
        all_warnings.extend(img_errors)

    for w in all_warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")

    return "\n\n".join(context_parts), valid_images
