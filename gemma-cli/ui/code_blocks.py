"""F-006 / C-002: 코드블록 저장 제안 · 실행 제안"""
from __future__ import annotations

from rich.console import Console

from core.code_runner import run_code_block, is_runnable_lang
from core.file_handler import extract_code_blocks, write_file_with_backup, get_file_diff_preview
from core.git_handler import is_git_repo
from utils.selector import select

console = Console()


def prompt_save_code_blocks(response: str) -> None:
    """F-006: AI 응답에 코드블록이 있으면 저장 여부 질문"""
    blocks = extract_code_blocks(response)
    if not blocks:
        return

    console.print()
    console.print(f"[dim]코드블록 {len(blocks)}개 감지됨.[/dim]")

    for i, block in enumerate(blocks, 1):
        lang = block["lang"] or "텍스트"
        suggested = block["suggested_filename"]
        code = block["code"]
        lines = code.count("\n") + 1

        console.print(f"\n[bold][{i}/{len(blocks)}] {lang} 코드 ({lines}줄)[/bold]")
        console.print(f"[dim]제안 파일명: [cyan]{suggested}[/cyan][/dim]")

        try:
            action = select(
                "어떻게 할까요?",
                [
                    ("save",   f"저장  →  {suggested}"),
                    ("rename", "다른 이름으로 저장"),
                    ("skip",   "건너뜀"),
                ],
            )
        except (EOFError, KeyboardInterrupt):
            break

        if action is None or action == "skip":
            continue

        if action == "rename":
            try:
                filename = console.input("  파일명: ").strip()
                if not filename:
                    continue
            except (EOFError, KeyboardInterrupt):
                continue
        else:
            filename = suggested

        diff_preview = get_file_diff_preview(filename, code)
        if diff_preview and diff_preview != f"[새 파일] {filename}":
            console.print("[dim]--- 변경 내용 미리보기 ---[/dim]")
            preview_lines = diff_preview.splitlines()[:20]
            for line in preview_lines:
                if line.startswith("+"):
                    console.print(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    console.print(f"[red]{line}[/red]")
                else:
                    console.print(f"[dim]{line}[/dim]")
            if len(diff_preview.splitlines()) > 20:
                console.print(f"[dim]... 외 {len(diff_preview.splitlines()) - 20}줄[/dim]")
        else:
            console.print(f"[dim][새 파일] {filename}[/dim]")

        ok, msg = write_file_with_backup(filename, code)
        if ok:
            console.print(f"[green]✔ {msg}[/green]")

            if is_git_repo():
                git_action = select("git add 할까요?", [("yes", "Yes"), ("no", "No")], default=0)
                if git_action == "yes":
                    from core.git_handler import git_add
                    success, err = git_add(filename)
                    if success:
                        console.print(f"[green]✔ git add {filename}[/green]")
                    else:
                        console.print(f"[red]git add 실패: {err}[/red]")
        else:
            console.print(f"[red]✖ {msg}[/red]")


def prompt_run_code_blocks(response: str) -> None:
    """C-002: AI 응답 코드블록을 실행할지 질문"""
    blocks = extract_code_blocks(response)
    runnable = [b for b in blocks if is_runnable_lang(b["lang"])]

    if not runnable:
        return

    console.print()
    for block in runnable:
        lang = block["lang"]
        code = block["code"]
        lines = code.count("\n") + 1

        console.print(f"[bold][실행가능] {lang} 코드 ({lines}줄)[/bold]")
        try:
            action = select(
                "이 코드를 실행할까요?",
                [("run", "실행"), ("skip", "건너뜀")],
            )
        except (EOFError, KeyboardInterrupt):
            break

        if action != "run":
            continue

        console.print("[dim]실행 중...[/dim]")
        stdout, stderr, elapsed = run_code_block(lang, code)

        console.print(f"[dim](완료: {elapsed:.2f}초)[/dim]")
        if stdout:
            console.print(stdout, end="")
        if stderr:
            console.print(f"[red]{stderr}[/red]", end="")
        if not stdout and not stderr:
            console.print("[dim](출력 없음)[/dim]")
