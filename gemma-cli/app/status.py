"""상태 표시줄 · 컨텍스트 경고 · Git 상태"""
from __future__ import annotations

from rich.console import Console

from config.settings import get_settings
from core.git_handler import is_git_repo, get_branch, get_status_summary, get_vram_info

console = Console()


def build_status_bar(session, client, profile_name: str | None = None) -> str:
    settings = get_settings()
    ctx = settings.num_ctx
    tokens = session.token_estimate()
    pct = tokens / ctx * 100
    color = "green" if pct < 80 else ("yellow" if pct < 95 else "red")

    branch = get_branch() if is_git_repo() else "-"
    vram = get_vram_info()
    profile_str = f" | [magenta]{profile_name}[/magenta]" if profile_name else ""

    parts = [
        f"[dim]모델: [cyan]{client.model}[/cyan]",
        f"토큰: [{color}]{tokens:,}/{ctx:,}[/{color}] ({pct:.0f}%)",
        f"VRAM: [dim]{vram}[/dim]",
        f"브랜치: [yellow]{branch}[/yellow]{profile_str}[/dim]",
    ]
    return " | ".join(parts)


def check_context_warning(session) -> str | None:
    """T-002: 컨텍스트 한도 경고 반환"""
    settings = get_settings()
    ctx = settings.num_ctx
    tokens = session.token_estimate()
    pct = tokens / ctx

    if pct >= settings.get("context_warn_red", 0.95):
        return f"[red bold]경고: 컨텍스트 {pct*100:.0f}% 사용 중 (위험). /compress 로 압축하세요.[/red bold]"
    elif pct >= settings.get("context_warn_yellow", 0.80):
        return f"[yellow]주의: 컨텍스트 {pct*100:.0f}% 사용 중. /compress 를 권장합니다.[/yellow]"
    return None


def show_git_status_on_start() -> None:
    """G-001: 시작 시 Git 상태 표시"""
    settings = get_settings()
    if not settings.get("git_status_on_start", True):
        return
    if not is_git_repo():
        return

    branch = get_branch()
    summary = get_status_summary()

    if summary:
        console.print(f"[dim]Git 브랜치: [yellow]{branch}[/yellow]  변경 파일:[/dim]")
        console.print(f"[dim]{summary}[/dim]")
    else:
        console.print(f"[dim]Git 브랜치: [yellow]{branch}[/yellow]  변경 없음[/dim]")
