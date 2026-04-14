"""G-003: AI 생성 커밋 메시지 확인 후 실행"""
from __future__ import annotations

import re

from rich.console import Console

from core.git_handler import git_commit

console = Console()


def handle_commit_response(commit_msg: str) -> None:
    """AI가 생성한 커밋 메시지 확인 후 git commit 실행"""
    m = re.search(r"```[^\n]*\n(.+?)```", commit_msg, re.DOTALL)
    if m:
        clean_msg = m.group(1).strip()
    else:
        lines = [l.strip() for l in commit_msg.splitlines() if l.strip()]
        clean_msg = lines[0] if lines else commit_msg.strip()

    console.print(f"\n[bold]생성된 커밋 메시지:[/bold]")
    console.print(f"  [cyan]{clean_msg}[/cyan]")

    try:
        ans = console.input("\n이 메시지로 커밋할까요? [y/N/수정] ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not ans or ans.lower() == "n":
        console.print("[dim]커밋 취소됨.[/dim]")
        return

    final_msg = clean_msg if ans.lower() == "y" else ans

    success, out = git_commit(final_msg)
    if success:
        console.print(f"[green]✔ 커밋 완료: {out}[/green]")
    else:
        console.print(f"[red]✖ 커밋 실패: {out}[/red]")
