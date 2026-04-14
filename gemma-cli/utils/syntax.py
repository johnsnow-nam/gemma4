"""Rich 마크다운/코드 렌더링 헬퍼"""
from __future__ import annotations

import re
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()


def render_markdown(text: str) -> None:
    """마크다운 전체 렌더링"""
    console.print(Markdown(text))


def render_streaming_chunk(chunk: str) -> None:
    """스트리밍 토큰 즉시 출력 (줄바꿈 없이)"""
    console.print(chunk, end="", markup=False)


def render_panel(content: str, title: str = "", style: str = "blue") -> None:
    console.print(Panel(content, title=title, border_style=style))


def render_warning(msg: str) -> None:
    console.print(f"[yellow]⚠ {msg}[/yellow]")


def render_error(msg: str) -> None:
    console.print(f"[red]✖ {msg}[/red]")


def render_success(msg: str) -> None:
    console.print(f"[green]✔ {msg}[/green]")


def render_info(msg: str) -> None:
    console.print(f"[cyan]ℹ {msg}[/cyan]")
