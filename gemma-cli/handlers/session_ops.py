"""D-005 / F-005: 대화 압축 · 파일 감시"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from rich.console import Console

console = Console()


def compress_session(session, client) -> None:
    """D-005: 이전 대화를 AI가 요약하여 히스토리 교체"""
    msgs = session.messages
    system_msg = msgs[0] if msgs and msgs[0]["role"] == "system" else None
    user_msgs = [m for m in msgs if m["role"] != "system"]

    if len(user_msgs) < 2:
        console.print("[yellow]압축할 대화가 충분하지 않습니다.[/yellow]")
        return

    summary_msgs = [
        {"role": "system", "content": "당신은 대화 요약 전문가입니다."},
        {
            "role": "user",
            "content": (
                "다음 대화를 핵심만 요약해줘. "
                "중요한 결정, 코드, 파일 내용, 결론만 남기고 나머지는 생략해줘:\n\n"
                + "\n".join(
                    f"[{m['role'].upper()}]: {m['content'][:500]}" for m in user_msgs
                )
            ),
        },
    ]

    with console.status("[dim]대화 요약 중...[/dim]"):
        try:
            summary = client.chat_once(summary_msgs)
        except Exception as e:
            console.print(f"[red]요약 실패: {e}[/red]")
            return

    new_messages = []
    if system_msg:
        new_messages.append(system_msg)
    new_messages.append({
        "role": "user",
        "content": f"[이전 대화 요약]\n{summary}"
    })
    new_messages.append({
        "role": "assistant",
        "content": "이전 대화 내용을 요약해서 기억하겠습니다."
    })

    session.messages = new_messages
    console.print(
        f"[green]✔ 대화가 요약됐습니다. (메시지 {len(user_msgs)}개 → 요약본)[/green]"
    )


def start_file_watcher(file_path: str, callback: Callable) -> object | None:
    """F-005: watchdog으로 파일 변경 감지"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            def __init__(self, target: str, cb: Callable):
                super().__init__()
                self._target = os.path.abspath(target)
                self._cb = cb

            def on_modified(self, event):
                if not event.is_directory:
                    abs_src = os.path.abspath(event.src_path)
                    if abs_src == self._target:
                        self._cb(self._target)

        observer = Observer()
        handler = _Handler(file_path, callback)
        watch_dir = os.path.dirname(os.path.abspath(file_path))
        observer.schedule(handler, watch_dir, recursive=False)
        observer.start()
        return observer

    except ImportError:
        console.print("[red]watchdog 라이브러리가 없습니다. pip install watchdog[/red]")
        return None
    except Exception as e:
        console.print(f"[red]파일 감시 실패: {e}[/red]")
        return None
