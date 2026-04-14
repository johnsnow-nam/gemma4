"""시작 배너 — Claude Code 스타일 Woody Woodpecker"""
from __future__ import annotations

import getpass

from rich.columns import Columns
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel

console = Console()

_WOODPECKER = """\
[red]  ╱╲ ╱╲ ╱╲[/red]
[red]  ████████[/red]
[red] ██[/red][white]◎[/white][red]█████[/red][yellow]══►[/yellow]
[red] ███[/red][white]▄████[/white]
  [white]██████[/white]
[blue] ▄[/blue][white]██████[/white][blue]▄[/blue]
[blue]▐█[/blue][white]██████[/white][blue]█▌[/blue]
[blue] █[/blue][white]████[/white][blue]███[/blue]  [blue]▲[/blue]
[blue]  ██[/blue] [blue]███[/blue]
[yellow] ████ ████[/yellow]"""


def show_banner(
    client,
    ollama_ok: bool,
    model_count: int,
    mcp_connected: list[str],
    mcp_manager,
    active_profile_name: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    username = getpass.getuser()

    dry_tag     = "\n[yellow]  ⚠ DRY-RUN 모드[/yellow]" if dry_run else ""
    verbose_tag = "\n[dim]  VERBOSE 모드[/dim]" if verbose else ""
    profile_tag = (
        f"\n[dim]  프로파일: [cyan]{active_profile_name}[/cyan][/dim]"
        if active_profile_name else ""
    )
    ollama_tag = (
        f"\n[green]  ✔ Ollama  [dim]{model_count}개 모델[/dim][/green]"
        if ollama_ok else
        "\n[red]  ✖ Ollama 연결 실패[/red]"
    )

    if mcp_connected:
        total_tools = sum(len(mcp_manager.servers[s].tools) for s in mcp_connected)
        mcp_tag = (
            f"\n[green]  ✔ MCP  "
            f"[dim]{len(mcp_connected)}개 서버 · {total_tools}개 도구[/dim][/green]"
        )
    else:
        mcp_tag = "\n[dim]  MCP 서버 없음[/dim]"

    left = (
        f"\n{_WOODPECKER}\n\n"
        f"  [bold cyan]Welcome back, {username}![/bold cyan]\n"
    )
    right = (
        f"[bold]gemma-cli[/bold]  [dim]v1.0  로컬 AI CLI[/dim]\n"
        f"[dim]{'─' * 38}[/dim]\n"
        f"  모델  [cyan]{client.model}[/cyan]"
        f"{ollama_tag}"
        f"{mcp_tag}"
        f"{profile_tag}"
        f"{dry_tag}{verbose_tag}\n"
        f"[dim]{'─' * 38}[/dim]\n"
        f"[dim]  /help    도움말\n"
        f"  /mcp     MCP 도구\n"
        f"  @파일    파일 첨부\n"
        f"  !명령어  셸 실행\n"
        f"  Ctrl+D  종료[/dim]"
    )

    console.print(Panel(
        Columns(
            [Padding(left, (0, 2)), Padding(right, (1, 2))],
            equal=False,
            expand=True,
        ),
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()
