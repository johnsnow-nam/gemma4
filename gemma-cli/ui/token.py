"""T-001 / V-002: 토큰 미리보기 · dry-run 미리보기"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from config.settings import get_settings

console = Console()


def show_token_preview(message: str, session, verbose: bool = False) -> None:
    """T-001: 입력 전 토큰 수 미리보기"""
    settings = get_settings()
    ctx = settings.num_ctx
    msg_tokens = len(message) // 4
    total = session.token_estimate() + msg_tokens
    pct = total / ctx * 100

    if verbose or pct > 60:
        color = "green" if pct < 80 else ("yellow" if pct < 95 else "red")
        console.print(
            f"[dim]입력 토큰: ~{msg_tokens:,} | "
            f"총: [{color}]{total:,}/{ctx:,}[/{color}] ({pct:.0f}%)[/dim]"
        )


def dry_run_preview(
    message: str,
    file_refs: list[str],
    image_refs: list[str],
    model: str,
    session,
) -> None:
    """V-002: --dry-run 모드 미리보기"""
    settings = get_settings()
    ctx = settings.num_ctx
    tokens = session.token_estimate() + len(message) // 4

    console.print(Panel.fit(
        f"[bold yellow]DRY-RUN 미리보기[/bold yellow]\n"
        f"모델: [cyan]{model}[/cyan]\n"
        f"메시지: {len(message)}자 (~{len(message)//4} 토큰)\n"
        f"파일 참조: {file_refs}\n"
        f"이미지 참조: {image_refs}\n"
        f"예상 총 토큰: {tokens:,} / {ctx:,} ({tokens/ctx*100:.0f}%)",
        border_style="yellow",
    ))
