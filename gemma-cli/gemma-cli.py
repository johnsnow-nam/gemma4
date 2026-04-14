#!/usr/bin/env python3
"""
gemma-cli — Claude Code처럼 동작하는 로컬 AI CLI
gemma4 + Ollama 기반

실행: python3 gemma-cli.py [--model MODEL] [--url URL] [--dry-run] [--profile PROFILE]
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

from core.ollama_client import OllamaClient
from core.session import Session
from core.mcp_client import MCPManager
from core.file_handler import (
    parse_at_references, read_single_file, read_glob_pattern, read_folder,
    extract_code_blocks, write_file_with_backup, get_file_diff_preview,
)
from core.image_handler import validate_images, image_meta_text
from core.code_runner import run_shell, is_dangerous, run_code_block, is_runnable_lang
from commands.slash_commands import SlashCommandHandler
from config.settings import get_settings
from config.profiles import detect_local_profile, get_profile, create_profile
from core.git_handler import (
    is_git_repo, get_branch, get_status_summary, git_commit, get_vram_info,
)
from utils.selector import select, confirm

console = Console()

HISTORY_FILE = os.path.expanduser("~/.gemma-cli/history")
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

PROMPT_STYLE = Style.from_dict({
    "prompt":      "bold cyan",
    "prompt.user": "cyan",
})

SLASH_COMMANDS = [
    "/help", "/clear", "/retry", "/compress", "/copy", "/copy code",
    "/save", "/load", "/sessions", "/model", "/models", "/set",
    "/profile", "/profiles", "/run", "/watch", "/diff", "/commit",
    "/screenshot", "/ls", "/tokens", "/config", "/verbose", "/exit", "/quit",
    "/mcp", "/mcp list", "/mcp status", "/mcp reconnect", "/mcp tools",
]

# 자동 모델 라우팅 기준
MODEL_26B = "gemma4:26b"
MODEL_E4B = "gemma4:e4b"


# ---------------------------------------------------------------------------
# Tab 자동완성
# ---------------------------------------------------------------------------

class GemmaCompleter(Completer):
    """Tab 자동완성: /명령어 + @파일경로"""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        if word.startswith("/"):
            for cmd in SLASH_COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd[len(word):], display=cmd)

        elif word.startswith("@"):
            prefix = word[1:]
            base_dir = os.path.dirname(prefix) or "."
            partial = os.path.basename(prefix)
            try:
                for entry in sorted(os.listdir(os.path.expanduser(base_dir))):
                    if entry.startswith(partial):
                        full = os.path.join(base_dir, entry) if base_dir != "." else entry
                        is_dir = os.path.isdir(os.path.expanduser(full))
                        display = "@" + full + ("/" if is_dir else "")
                        yield Completion(
                            entry[len(partial):] + ("/" if is_dir else ""),
                            display=display,
                        )
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 상태 표시줄
# ---------------------------------------------------------------------------

def build_status_bar(session: Session, client: OllamaClient, profile_name: str | None = None) -> str:
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


def check_context_warning(session: Session) -> str | None:
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


# ---------------------------------------------------------------------------
# 자동 모델 라우팅 (M-003)
# ---------------------------------------------------------------------------

def select_model(base_model: str, message: str, has_images: bool, client: OllamaClient) -> str:
    """M-003: 메시지/이미지 기반 자동 모델 선택"""
    settings = get_settings()
    if not settings.auto_routing:
        return base_model

    if has_images:
        target = MODEL_26B
    elif len(message) > 2000:
        target = MODEL_26B
    else:
        # e4b가 있으면 빠른 모델 사용
        if client.is_model_available(MODEL_E4B):
            target = MODEL_E4B
        else:
            target = base_model

    return target


# ---------------------------------------------------------------------------
# 파일 @ 참조 처리
# ---------------------------------------------------------------------------

def process_at_references(
    file_refs: list[str],
    image_refs: list[str],
    client: OllamaClient,
    verbose: bool = False,
) -> tuple[str, list[str]]:
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


# ---------------------------------------------------------------------------
# 스트리밍 응답
# ---------------------------------------------------------------------------

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
    """경과 시간을 '1m 15s' 또는 '3.2s' 형식으로 변환"""
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    return f"{seconds:.1f}s"


def stream_response(
    session: Session,
    client: OllamaClient,
    image_paths: list[str],
    override_model: str | None = None,
    verbose: bool = False,
) -> str:
    """AI 응답 스트리밍 — Thinking 애니메이션 + 경과 시간 표시"""
    from rich.live import Live
    from rich.text import Text as RichText
    import itertools
    import queue
    import threading
    import time

    full_response = ""
    orig_model    = client.model
    t_start       = time.monotonic()

    if override_model and override_model != client.model:
        client.model = override_model
        if verbose:
            console.print(f"[dim]자동 라우팅 → {override_model}[/dim]")

    console.print()

    # ── Thinking 애니메이션 렌더러 ─────────────────────────────────────
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

    thinking_renderable._phrase = next(phrase_cycle)  # 함수 정의 후 초기화

    try:
        if verbose:
            console.print(f"[dim]요청: model={client.model}, msgs={len(session.messages)}, images={len(image_paths)}[/dim]")

        stats: dict = {}
        if image_paths:
            stream = client.chat_stream_with_images(session.messages, image_paths)
        else:
            stream = client.chat_stream(session.messages, stats=stats)

        # ── Phase 1: 첫 토큰 대기 중 Thinking 애니메이션 ─────────────
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

        t_first = time.monotonic()   # 첫 토큰 도착 시각

        # ── Phase 2: 토큰 스트리밍 출력 ──────────────────────────────
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

        # ── ✻ Cooked for · tokens · tok/s ───────────────────────────
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
        console.print(f"\n[yellow]⚠ 생성 중단됨[/yellow]  [dim]({_fmt_elapsed(t_end - t_start)})[/dim]")
    except Exception as e:
        console.print(f"\n[red]오류: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    finally:
        client.model = orig_model

    return full_response


# ---------------------------------------------------------------------------
# Tool Calling 응답 처리 (Phase A)
# ---------------------------------------------------------------------------

MAX_TOOL_ROUNDS = 5  # 무한 루프 방지


def run_with_tools(
    session: Session,
    client: OllamaClient,
    mcp_manager: MCPManager,
    verbose: bool = False,
) -> str:
    """Tool Calling 루프:
    1. Gemma 호출 (tools 포함)
    2. tool_calls 있으면 → MCP 실행 → 결과 추가 → 반복
    3. 최종 텍스트 응답 반환
    """
    tools = mcp_manager.to_ollama_tools()
    if not tools:
        # 도구 없으면 일반 스트리밍
        return stream_response(session, client, [], verbose=verbose)

    full_response = ""

    for round_num in range(MAX_TOOL_ROUNDS):
        if verbose:
            console.print(f"[dim]Tool round {round_num + 1}/{MAX_TOOL_ROUNDS}[/dim]")

        try:
            text, tool_calls = client.chat_with_tools(session.messages, tools)
        except Exception as e:
            console.print(f"[red]Tool Calling 오류: {e}[/red]")
            # fallback: 일반 스트리밍
            return stream_response(session, client, [], verbose=verbose)

        # 도구 호출이 없으면 최종 응답
        if not tool_calls:
            if text:
                console.print()
                console.print("[dim cyan]gemma[/dim cyan] ", end="")
                console.print(text, markup=False)
                console.print()
            full_response = text
            break

        # Gemma의 어시스턴트 메시지(tool_calls 포함) 저장
        session.messages.append({
            "role": "assistant",
            "content": text or "",
            "tool_calls": tool_calls,
        })

        # 도구 실행 및 결과 표시
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "?")
            args = fn.get("arguments", {})
            console.print(f"\n[dim cyan]⚙ MCP 도구 호출:[/dim cyan] [cyan]{name}[/cyan]", end="")
            if args:
                console.print(f"  [dim]{args}[/dim]", end="")
            console.print()

        tool_messages = mcp_manager.execute_tool_calls(tool_calls)

        for msg in tool_messages:
            result_preview = msg["content"][:200]
            console.print(f"[dim]  → {result_preview}{'...' if len(msg['content']) > 200 else ''}[/dim]")
            session.messages.append(msg)

    return full_response


# ---------------------------------------------------------------------------
# 파일 쓰기 프롬프트 (F-006)
# ---------------------------------------------------------------------------

def prompt_save_code_blocks(response: str) -> None:
    """AI 응답에 코드블록이 있으면 저장 여부 질문 (인라인 선택 UI)"""
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
                f"어떻게 할까요?",
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

        # 파일명 결정
        if action == "rename":
            try:
                filename = console.input("  파일명: ").strip()
                if not filename:
                    continue
            except (EOFError, KeyboardInterrupt):
                continue
        else:
            filename = suggested

        # diff 미리보기
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

        # 저장
        ok, msg = write_file_with_backup(filename, code)
        if ok:
            console.print(f"[green]✔ {msg}[/green]")

            # git add 여부
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


# ---------------------------------------------------------------------------
# AI 생성 코드 실행 제안 (C-002)
# ---------------------------------------------------------------------------

def prompt_run_code_blocks(response: str) -> None:
    """AI 응답 코드블록을 실행할지 질문 (인라인 선택 UI)"""
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

        console.print(f"[dim]실행 중...[/dim]")
        stdout, stderr, elapsed = run_code_block(lang, code)

        console.print(f"[dim](완료: {elapsed:.2f}초)[/dim]")
        if stdout:
            console.print(stdout, end="")
        if stderr:
            console.print(f"[red]{stderr}[/red]", end="")
        if not stdout and not stderr:
            console.print("[dim](출력 없음)[/dim]")


# ---------------------------------------------------------------------------
# 셸 명령어 처리
# ---------------------------------------------------------------------------

def handle_shell_command(cmd: str, verbose: bool = False) -> str:
    """!명령어 처리 (C-003)"""
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


# ---------------------------------------------------------------------------
# 대화 압축 (D-005)
# ---------------------------------------------------------------------------

def compress_session(session: Session, client: OllamaClient) -> None:
    """이전 대화를 AI가 요약하여 히스토리 교체"""
    msgs = session.messages
    system_msg = msgs[0] if msgs and msgs[0]["role"] == "system" else None
    user_msgs = [m for m in msgs if m["role"] != "system"]

    if len(user_msgs) < 2:
        console.print("[yellow]압축할 대화가 충분하지 않습니다.[/yellow]")
        return

    # 요약 요청
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

    # 히스토리 교체
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
    console.print(f"[green]✔ 대화가 요약됐습니다. (메시지 {len(user_msgs)}개 → 요약본)[/green]")


# ---------------------------------------------------------------------------
# 파일 감시 (F-005)
# ---------------------------------------------------------------------------

def start_file_watcher(file_path: str, callback) -> object | None:
    """watchdog으로 파일 변경 감지"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            def __init__(self, target: str, cb):
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


# ---------------------------------------------------------------------------
# 커밋 확인 후 실행
# ---------------------------------------------------------------------------

def handle_commit_response(commit_msg: str) -> None:
    """G-003: AI가 생성한 커밋 메시지 확인 후 실행"""
    # 코드블록에서 메시지 추출
    import re
    m = re.search(r"```[^\n]*\n(.+?)```", commit_msg, re.DOTALL)
    if m:
        clean_msg = m.group(1).strip()
    else:
        # 첫 번째 비어있지 않은 줄 추출
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

    if ans.lower() == "y":
        final_msg = clean_msg
    else:
        final_msg = ans

    success, out = git_commit(final_msg)
    if success:
        console.print(f"[green]✔ 커밋 완료: {out}[/green]")
    else:
        console.print(f"[red]✖ 커밋 실패: {out}[/red]")


# ---------------------------------------------------------------------------
# 토큰 미리보기 (T-001)
# ---------------------------------------------------------------------------

def show_token_preview(message: str, session: Session, verbose: bool = False) -> None:
    """T-001: 입력 전 토큰 수 미리보기"""
    settings = get_settings()
    ctx = settings.num_ctx
    msg_tokens = len(message) // 4
    total = session.token_estimate() + msg_tokens
    pct = total / ctx * 100

    if verbose or pct > 60:
        color = "green" if pct < 80 else ("yellow" if pct < 95 else "red")
        console.print(
            f"[dim]입력 토큰: ~{msg_tokens:,} | 총: [{color}]{total:,}/{ctx:,}[/{color}] ({pct:.0f}%)[/dim]"
        )


# ---------------------------------------------------------------------------
# dry-run 처리
# ---------------------------------------------------------------------------

def dry_run_preview(
    message: str,
    file_refs: list[str],
    image_refs: list[str],
    model: str,
    session: Session,
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


# ---------------------------------------------------------------------------
# G-001: Git 상태 초기 표시
# ---------------------------------------------------------------------------

def show_git_status_on_start() -> None:
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


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="gemma-cli — 로컬 AI CLI")
    parser.add_argument("--model", default=None, help="사용할 모델 이름")
    parser.add_argument("--url", default=None, help="Ollama 서버 URL")
    parser.add_argument("--profile", default=None, help="프로파일 이름")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 입력 구성 확인")
    parser.add_argument("--verbose", action="store_true", help="API 요청/응답 상세 출력")
    args = parser.parse_args()

    # 설정 로드
    settings = get_settings()
    model = args.model or settings.model
    url = args.url or settings.ollama_url
    dry_run = args.dry_run
    verbose = args.verbose

    # 초기화
    client = OllamaClient(
        model=model,
        base_url=url,
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        top_p=settings.top_p,
        repeat_penalty=settings.repeat_penalty,
    )
    session = Session(model=model)

    # MCP 클라이언트 초기화
    mcp_manager = MCPManager()
    if not dry_run:
        with console.status("[dim]MCP 서버 연결 중...[/dim]"):
            connected = mcp_manager.load_and_connect()
    else:
        connected = []

    cmd_handler = SlashCommandHandler(session, client, mcp_manager=mcp_manager)
    cmd_handler._verbose = verbose

    # 프로파일 로드 (우선순위: --profile > 로컬 .gemma-cli > 없음)
    active_profile_name: str | None = None

    profile_name = args.profile or detect_local_profile()
    if profile_name:
        profile = get_profile(profile_name)
        if profile:
            cmd_handler._apply_profile(profile)
            active_profile_name = profile_name
            console.print(f"[dim]프로파일 로드: [cyan]{profile_name}[/cyan][/dim]")
        else:
            console.print(f"[yellow]프로파일을 찾을 수 없습니다: {profile_name}[/yellow]")

    # prompt_toolkit 세션
    prompt_session = PromptSession(
        history=FileHistory(HISTORY_FILE),
        auto_suggest=AutoSuggestFromHistory(),
        completer=GemmaCompleter(),
        style=PROMPT_STYLE,
        multiline=False,
    )

    # ── Ollama 연결 확인 (배너 전에 수행) ──────────────────────────────
    if not dry_run:
        with console.status("[dim]Ollama 연결 확인 중...[/dim]"):
            models = client.list_models()
        ollama_ok = bool(models)
        model_count = len(models)
    else:
        ollama_ok = True
        model_count = 0

    # ── 시작 배너 (Claude Code 스타일) ────────────────────────────────
    import getpass
    username = getpass.getuser()

    WOODPECKER = """\
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

    dry_tag    = "\n[yellow]  ⚠ DRY-RUN 모드[/yellow]" if dry_run else ""
    verbose_tag = "\n[dim]  VERBOSE 모드[/dim]" if verbose else ""
    profile_tag = f"\n[dim]  프로파일: [cyan]{active_profile_name}[/cyan][/dim]" if active_profile_name else ""
    ollama_tag  = (
        f"\n[green]  ✔ Ollama  [dim]{model_count}개 모델[/dim][/green]"
        if ollama_ok else
        "\n[red]  ✖ Ollama 연결 실패[/red]"
    )
    if connected:
        total_tools = sum(len(mcp_manager.servers[s].tools) for s in connected)
        mcp_tag = f"\n[green]  ✔ MCP  [dim]{len(connected)}개 서버 · {total_tools}개 도구[/dim][/green]"
    else:
        mcp_tag = "\n[dim]  MCP 서버 없음[/dim]"

    left = (
        f"\n{WOODPECKER}\n\n"
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

    from rich.columns import Columns
    from rich.padding import Padding

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

    # G-001: Git 상태
    show_git_status_on_start()

    console.print()

    # 파일 감시 관리
    active_watchers: list[object] = []
    watch_callbacks: dict[str, bool] = {}

    def _on_file_changed(fpath: str) -> None:
        watch_callbacks[fpath] = True
        console.print(f"\n[yellow]파일이 변경됐습니다: {fpath}[/yellow]")
        console.print("[yellow]다시 분석하려면 Enter를 누르세요.[/yellow]")

    # 메인 루프
    while True:
        # 파일 변경 감지 처리
        for fpath, changed in list(watch_callbacks.items()):
            if changed:
                watch_callbacks[fpath] = False
                text, warns = read_single_file(fpath)
                for w in warns:
                    console.print(f"[yellow]⚠ {w}[/yellow]")
                session.add_user(f"파일이 변경됐습니다. 다시 분석해줘:\n\n{text}")
                full = stream_response(session, client, [], verbose=verbose)
                if full:
                    session.add_assistant(full)
                    cmd_handler.set_last_response(full)

        # 상태 표시줄
        console.print(build_status_bar(session, client, active_profile_name))

        # 컨텍스트 경고
        warn = check_context_warning(session)
        if warn:
            console.print(warn)

        # 사용자 입력
        branch = get_branch() if is_git_repo() else ""
        branch_tag = f"[{branch}] " if branch and branch != "-" else ""

        try:
            user_input = prompt_session.prompt(
                [("class:prompt", f"{branch_tag}나 > ")],
                style=PROMPT_STYLE,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            action = select(
                "gemma-cli를 종료할까요?",
                [("quit", "종료"), ("continue", "계속 사용")],
                default=0,
            )
            if action == "quit" or action is None:
                console.print("[yellow]종료합니다.[/yellow]")
                break
            continue

        if not user_input:
            continue

        # ----------------------------------------------------------------
        # 슬래시 명령어
        # ----------------------------------------------------------------
        if user_input.startswith("/"):
            result = cmd_handler.handle(user_input)

            if result.handled:
                if result.output:
                    console.print(result.output)
                if result.quit:
                    break
                if result.clear_session:
                    console.print()
                if result.verbose_toggle:
                    verbose = cmd_handler._verbose
                if result.watch_file:
                    obs = start_file_watcher(result.watch_file, _on_file_changed)
                    if obs:
                        active_watchers.append(obs)
                        watch_callbacks[result.watch_file] = False

                # D-005 /compress
                if result.compress:
                    compress_session(session, client)
                    continue

                # D-004 /retry
                if result.retry:
                    last_user = next(
                        (m for m in reversed(session.messages) if m["role"] == "user"), None
                    )
                    if last_user:
                        if not dry_run:
                            full = stream_response(session, client, [], verbose=verbose)
                            if full:
                                session.add_assistant(full)
                                cmd_handler.set_last_response(full)
                                prompt_save_code_blocks(full)
                    continue

                # /mcp 재연결
                if result.extra.get("mcp_reconnect"):
                    with console.status("[dim]MCP 서버 재연결 중...[/dim]"):
                        mcp_manager.disconnect_all()
                        reconnected = mcp_manager.load_and_connect()
                    cmd_handler.mcp = mcp_manager
                    if reconnected:
                        total_tools = sum(len(mcp_manager.servers[s].tools) for s in reconnected)
                        console.print(f"[green]✔ MCP 재연결: {len(reconnected)}개 서버 · {total_tools}개 도구[/green]")
                    else:
                        console.print("[yellow]연결된 서버 없음[/yellow]")
                    continue

                # /mcp <서버> <도구> 직접 실행
                if result.extra.get("mcp_call"):
                    mcp_req = result.extra["mcp_call"]
                    srv_name = mcp_req["server"]
                    tool_name = mcp_req["tool"]
                    tool_args = mcp_req["args"]

                    console.print(f"[dim cyan]⚙ {srv_name} · {tool_name}[/dim cyan]  [dim]{tool_args or ''}[/dim]")
                    with console.status(f"[dim]{tool_name} 실행 중...[/dim]"):
                        tool_result = mcp_manager.call_tool(srv_name, tool_name, tool_args)

                    # 결과 출력
                    console.print(f"\n[dim cyan]gemma[/dim cyan] 도구 실행 결과:\n")
                    console.print(tool_result)
                    console.print()

                    # 세션에 추가해서 후속 대화 가능
                    session.add_user(f"[MCP {srv_name}/{tool_name}] 도구 실행 결과:\n{tool_result}")
                    session.add_assistant(tool_result)
                    cmd_handler.set_last_response(tool_result)
                    continue

                # AI 응답이 필요한 명령어 (/diff, /commit, /run, /screenshot)
                if result.needs_ai and result.ai_prompt:
                    extra = result.extra or {}

                    # 스크린샷 이미지 처리
                    img_paths = []
                    if "screenshot_path" in extra:
                        img_paths = [extra["screenshot_path"]]

                    session.add_user(result.ai_prompt)
                    if not dry_run:
                        full = stream_response(session, client, img_paths, verbose=verbose)
                        if full:
                            session.add_assistant(full)
                            cmd_handler.set_last_response(full)

                            # /commit 후 커밋 확인
                            if extra.get("commit_mode"):
                                handle_commit_response(full)
                    else:
                        dry_run_preview(result.ai_prompt, [], img_paths, client.model, session)
                    continue

                # 프로파일 create
                if result.extra.get("profile_create"):
                    pname = result.extra["profile_create"]
                    console.print(f"[bold]프로파일 '[cyan]{pname}[/cyan]' 생성[/bold]")
                    try:
                        desc = console.input("  설명: ").strip()
                        sys_prompt = console.input("  시스템 프롬프트: ").strip()
                        mdl = console.input(f"  모델 [{client.model}]: ").strip() or client.model
                    except (EOFError, KeyboardInterrupt):
                        console.print("[yellow]취소됨.[/yellow]")
                        continue
                    path = create_profile(pname, {
                        "description": desc,
                        "system_prompt": sys_prompt,
                        "model": mdl,
                        "file_patterns": [],
                        "root_path": None,
                    })
                    console.print(f"[green]✔ 프로파일 저장: {path}[/green]")

                continue
            else:
                console.print(f"[red]알 수 없는 명령어: {user_input}[/red]  [dim]/help 참조[/dim]")
                continue

        # ----------------------------------------------------------------
        # 셸 명령어 (! 접두사)
        # ----------------------------------------------------------------
        if user_input.startswith("!"):
            shell_output = handle_shell_command(user_input, verbose=verbose)
            if shell_output:
                session.add_user(f"셸 명령어 실행 결과:\n```\n{shell_output}\n```")
                if not dry_run:
                    full = stream_response(session, client, [], verbose=verbose)
                    if full:
                        session.add_assistant(full)
                        cmd_handler.set_last_response(full)
            continue

        # ----------------------------------------------------------------
        # 클립보드 이미지 감지 (I-003) — @clipboard 키워드
        # ----------------------------------------------------------------
        clipboard_image = None
        if "@clipboard" in user_input:
            from core.image_handler import get_clipboard_image
            with console.status("[dim]클립보드에서 이미지 가져오는 중...[/dim]"):
                clipboard_image = get_clipboard_image()
            if clipboard_image:
                console.print(f"[green]클립보드 이미지: {clipboard_image}[/green]")
                user_input = user_input.replace("@clipboard", "").strip()
            else:
                console.print("[yellow]클립보드에 이미지가 없습니다.[/yellow]")

        # ----------------------------------------------------------------
        # @ 참조 파싱
        # ----------------------------------------------------------------
        clean_prompt, file_refs, image_refs = parse_at_references(user_input)

        if clipboard_image:
            image_refs.append(clipboard_image)

        context_text = ""
        valid_images: list[str] = []

        if file_refs or image_refs:
            with console.status("[dim]파일 읽는 중...[/dim]"):
                context_text, valid_images = process_at_references(
                    file_refs, image_refs, client, verbose=verbose
                )

        # 이미지 메타 표시
        if valid_images:
            console.print(image_meta_text(valid_images))

        # 사용자 메시지 구성
        if context_text and clean_prompt:
            full_message = f"{context_text}\n\n---\n\n{clean_prompt}"
        elif context_text:
            full_message = f"{context_text}\n\n위 내용을 분석해줘."
        else:
            full_message = user_input

        # T-001: 토큰 미리보기
        show_token_preview(full_message, session, verbose=verbose)

        # dry-run 미리보기
        if dry_run:
            dry_run_preview(full_message, file_refs, image_refs, client.model, session)
            continue

        # M-003: 자동 모델 라우팅
        routed_model = select_model(client.model, full_message, bool(valid_images), client)
        if routed_model != client.model and verbose:
            console.print(f"[dim]자동 라우팅: {client.model} → {routed_model}[/dim]")

        session.add_user(full_message)

        # AI 응답 — Tool Calling 활성 시 MCP 도구 자동 사용 (Phase A)
        use_tools = (
            cmd_handler.mcp_tools_enabled
            and mcp_manager.servers
            and not valid_images  # 이미지는 tool calling 미지원
        )

        if use_tools:
            full_response = run_with_tools(session, client, mcp_manager, verbose=verbose)
        else:
            full_response = stream_response(
                session, client, valid_images,
                override_model=routed_model if routed_model != client.model else None,
                verbose=verbose,
            )

        if full_response:
            session.add_assistant(full_response)
            cmd_handler.set_last_response(full_response)
            console.print()

            # F-006: 코드블록 감지 후 저장 제안
            prompt_save_code_blocks(full_response)

            # C-002: 실행 가능 코드 실행 제안
            prompt_run_code_blocks(full_response)

    # 감시 중지
    for obs in active_watchers:
        try:
            obs.stop()  # type: ignore[attr-defined]
            obs.join()  # type: ignore[attr-defined]
        except Exception:
            pass

    # MCP 연결 해제
    mcp_manager.disconnect_all()


if __name__ == "__main__":
    main()
