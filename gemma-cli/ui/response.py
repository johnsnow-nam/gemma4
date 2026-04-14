"""AI 응답 스트리밍 — Thinking 애니메이션 + 토큰 통계"""
from __future__ import annotations

import itertools
import queue
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text as RichText

console = Console()

_THINKING_PHRASES = [
    "컨텍스트를 파악하는 중",
    "코드를 분석하는 중",
    "최적의 답변을 구성하는 중",
    "관련 패턴을 탐색하는 중",
    "논리를 검증하는 중",
    "메모리에서 참조하는 중",
    "응답을 생성하는 중",
]

_SPINNER_FRAMES = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]


def _fmt_elapsed(seconds: float) -> str:
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    return f"{seconds:.1f}s"


def stream_response(
    session,
    client,
    image_paths: list[str],
    override_model: str | None = None,
    verbose: bool = False,
) -> str:
    """AI 응답 스트리밍 — Thinking 애니메이션 + 경과 시간 표시"""
    full_response = ""
    orig_model    = client.model
    t_start       = time.monotonic()

    if override_model and override_model != client.model:
        client.model = override_model
        if verbose:
            console.print(f"[dim]자동 라우팅 → {override_model}[/dim]")

    console.print()

    spinner_cycle  = itertools.cycle(_SPINNER_FRAMES)
    phrase_cycle   = itertools.cycle(_THINKING_PHRASES)
    phrase_counter = [0]

    def thinking_renderable() -> RichText:
        phrase_counter[0] += 1
        if phrase_counter[0] % 8 == 0:
            thinking_renderable._phrase = next(phrase_cycle)
        elapsed = time.monotonic() - t_start
        t = RichText()
        t.append("  ")
        t.append(next(spinner_cycle), style="bold cyan")
        t.append("  gemma  ",         style="dim cyan")
        t.append(thinking_renderable._phrase, style="dim")
        t.append(" ...",              style="dim")
        t.append(f"  [{_fmt_elapsed(elapsed)}]", style="dim bright_black")
        return t

    thinking_renderable._phrase = next(phrase_cycle)

    try:
        if verbose:
            console.print(
                f"[dim]요청: model={client.model}, msgs={len(session.messages)}, "
                f"images={len(image_paths)}[/dim]"
            )

        stats: dict = {}
        if image_paths:
            stream = client.chat_stream_with_images(session.messages, image_paths)
        else:
            stream = client.chat_stream(session.messages, stats=stats)

        token_q: queue.Queue = queue.Queue()

        def _fetch():
            try:
                for tok in stream:
                    token_q.put(tok)
            finally:
                token_q.put(None)

        threading.Thread(target=_fetch, daemon=True).start()

        first_token = None
        with Live(
            thinking_renderable(),
            console=console,
            refresh_per_second=20,
            transient=True,
        ) as live:
            while True:
                live.update(thinking_renderable())
                try:
                    tok = token_q.get(timeout=0.05)
                    if tok is not None:
                        first_token = tok
                    break
                except queue.Empty:
                    continue

        t_first = time.monotonic()

        console.print("[dim cyan]gemma[/dim cyan] ", end="")

        if first_token:
            console.print(first_token, end="", markup=False)
            full_response += first_token

        while True:
            tok = token_q.get()
            if tok is None:
                break
            console.print(tok, end="", markup=False)
            full_response += tok

        console.print()

        # ✻ Cooked for 푸터
        t_end         = time.monotonic()
        total_elapsed = t_end - t_start
        wait_elapsed  = t_first - t_start

        out_tok = stats.get("output_tokens", 0)
        in_tok  = stats.get("input_tokens",  0)
        tps     = stats.get("tokens_per_sec", 0)

        cooked = RichText()
        cooked.append("\n  ✻ ", style="dim cyan")
        cooked.append("Cooked for ", style="dim")
        cooked.append(_fmt_elapsed(total_elapsed), style="dim bold")

        if out_tok:
            cooked.append("  ·  ", style="dim bright_black")
            cooked.append(f"{in_tok:,}", style="dim")
            cooked.append(" → ", style="dim bright_black")
            cooked.append(f"{out_tok:,} tokens", style="dim bold")

        if tps:
            cooked.append("  ·  ", style="dim bright_black")
            cooked.append(f"{tps:.0f} tok/s", style="dim")

        if verbose:
            cooked.append(
                f"  ·  대기 {_fmt_elapsed(wait_elapsed)}",
                style="dim bright_black",
            )

        console.print(cooked)

    except KeyboardInterrupt:
        t_end = time.monotonic()
        console.print(
            f"\n[yellow]⚠ 생성 중단됨[/yellow]  "
            f"[dim]({_fmt_elapsed(t_end - t_start)})[/dim]"
        )
    except Exception as e:
        console.print(f"\n[red]오류: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    finally:
        client.model = orig_model

    return full_response
