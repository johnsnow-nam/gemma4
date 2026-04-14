"""C-003: ! 셸 명령어 실행"""
from __future__ import annotations

from rich.console import Console

from core.code_runner import run_shell, is_dangerous
from utils.selector import select

console = Console()


def handle_shell_command(cmd: str, verbose: bool = False) -> str:
    """!명령어 처리"""
    cmd = cmd[1:].strip()

    if is_dangerous(cmd):
        console.print(f"[red bold]⚠ 위험한 명령어: {cmd}[/red bold]")
        action = select(
            "정말 실행할까요?",
            [("no", "취소 (안전)"), ("yes", "실행")],
            default=0,
        )
        if action != "yes":
            return ""

    if verbose:
        console.print(f"[dim]셸 실행: {cmd}[/dim]")
    else:
        console.print(f"[dim]$ {cmd}[/dim]")

    stdout, stderr, elapsed = run_shell(cmd)

    output_parts = []
    if stdout:
        console.print(stdout, end="")
        output_parts.append(stdout)
    if stderr:
        console.print(f"[red]{stderr}[/red]", end="")
        output_parts.append(f"[stderr]\n{stderr}")

    console.print(f"[dim](완료: {elapsed:.2f}초)[/dim]")
    return "\n".join(output_parts)
