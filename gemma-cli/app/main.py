"""메인 이벤트 루프"""
from __future__ import annotations

import argparse
import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console

from app.banner import show_banner
from app.completer import GemmaCompleter
from app.routing import select_model
from app.status import build_status_bar, check_context_warning, show_git_status_on_start
from commands.slash_commands import SlashCommandHandler
from config.profiles import detect_local_profile, get_profile, create_profile
from config.settings import get_settings
from core.file_handler import parse_at_references
from core.git_handler import is_git_repo, get_branch, git_commit
from core.image_handler import image_meta_text
from core.mcp_client import MCPManager
from core.ollama_client import OllamaClient
from core.session import Session
from handlers.at_refs import process_at_references
from handlers.commit import handle_commit_response
from handlers.mcp_tools import run_with_tools
from handlers.session_ops import compress_session, start_file_watcher
from handlers.shell import handle_shell_command
from ui.code_blocks import prompt_save_code_blocks, prompt_run_code_blocks
from ui.response import stream_response
from ui.token import show_token_preview, dry_run_preview

console = Console()

HISTORY_FILE = os.path.expanduser("~/.gemma-cli/history")
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

PROMPT_STYLE = Style.from_dict({
    "prompt":      "bold cyan",
    "prompt.user": "cyan",
})


def main() -> None:
    parser = argparse.ArgumentParser(description="gemma-cli — 로컬 AI CLI")
    parser.add_argument("--model",    default=None, help="사용할 모델 이름")
    parser.add_argument("--url",      default=None, help="Ollama 서버 URL")
    parser.add_argument("--profile",  default=None, help="프로파일 이름")
    parser.add_argument("--dry-run",  action="store_true", help="API 호출 없이 입력 구성 확인")
    parser.add_argument("--verbose",  action="store_true", help="API 요청/응답 상세 출력")
    args = parser.parse_args()

    settings  = get_settings()
    model     = args.model or settings.model
    url       = args.url or settings.ollama_url
    dry_run   = args.dry_run
    verbose   = args.verbose

    # ── 핵심 객체 초기화 ──────────────────────────────────────────────
    client  = OllamaClient(
        model=model, base_url=url,
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        top_p=settings.top_p,
        repeat_penalty=settings.repeat_penalty,
    )
    session = Session(model=model)

    # ── MCP 클라이언트 초기화 ─────────────────────────────────────────
    mcp_manager = MCPManager()
    if not dry_run:
        with console.status("[dim]MCP 서버 연결 중...[/dim]"):
            mcp_connected = mcp_manager.load_and_connect()
    else:
        mcp_connected = []

    cmd_handler = SlashCommandHandler(session, client, mcp_manager=mcp_manager)
    cmd_handler._verbose = verbose

    # ── 프로파일 로드 ─────────────────────────────────────────────────
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

    # ── prompt_toolkit 세션 ───────────────────────────────────────────
    prompt_session = PromptSession(
        history=FileHistory(HISTORY_FILE),
        auto_suggest=AutoSuggestFromHistory(),
        completer=GemmaCompleter(),
        style=PROMPT_STYLE,
        multiline=False,
    )

    # ── Ollama 연결 확인 ──────────────────────────────────────────────
    if not dry_run:
        with console.status("[dim]Ollama 연결 확인 중...[/dim]"):
            models = client.list_models()
        ollama_ok    = bool(models)
        model_count  = len(models)
    else:
        ollama_ok    = True
        model_count  = 0

    # ── 시작 배너 ─────────────────────────────────────────────────────
    show_banner(
        client, ollama_ok, model_count,
        mcp_connected, mcp_manager,
        active_profile_name, dry_run, verbose,
    )

    # ── Git 상태 ──────────────────────────────────────────────────────
    show_git_status_on_start()
    console.print()

    # ── 파일 감시 상태 ────────────────────────────────────────────────
    active_watchers: list[object] = []
    watch_callbacks: dict[str, bool] = {}

    def _on_file_changed(fpath: str) -> None:
        watch_callbacks[fpath] = True
        console.print(f"\n[yellow]파일이 변경됐습니다: {fpath}[/yellow]")
        console.print("[yellow]다시 분석하려면 Enter를 누르세요.[/yellow]")

    # ═══════════════════════════════════════════════════════════════════
    # 메인 루프
    # ═══════════════════════════════════════════════════════════════════
    while True:

        # ── 파일 변경 감지 ────────────────────────────────────────────
        for fpath, changed in list(watch_callbacks.items()):
            if changed:
                watch_callbacks[fpath] = False
                from core.file_handler import read_single_file
                text, warns = read_single_file(fpath)
                for w in warns:
                    console.print(f"[yellow]⚠ {w}[/yellow]")
                session.add_user(f"파일이 변경됐습니다. 다시 분석해줘:\n\n{text}")
                full = stream_response(session, client, [], verbose=verbose)
                if full:
                    session.add_assistant(full)
                    cmd_handler.set_last_response(full)

        # ── 상태 표시줄 ───────────────────────────────────────────────
        console.print(build_status_bar(session, client, active_profile_name))
        warn = check_context_warning(session)
        if warn:
            console.print(warn)

        # ── 사용자 입력 ───────────────────────────────────────────────
        branch = get_branch() if is_git_repo() else ""
        branch_tag = f"[{branch}] " if branch and branch != "-" else ""

        try:
            user_input = prompt_session.prompt(
                [("class:prompt", f"{branch_tag}나 > ")],
                style=PROMPT_STYLE,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            from utils.selector import select
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

        # ══════════════════════════════════════════════════════════════
        # 슬래시 명령어
        # ══════════════════════════════════════════════════════════════
        if user_input.startswith("/"):
            result = cmd_handler.handle(user_input)

            if not result.handled:
                console.print(f"[red]알 수 없는 명령어: {user_input}[/red]  [dim]/help 참조[/dim]")
                continue

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

            # /compress
            if result.compress:
                compress_session(session, client)
                continue

            # /retry
            if result.retry:
                last_user = next(
                    (m for m in reversed(session.messages) if m["role"] == "user"), None
                )
                if last_user and not dry_run:
                    full = stream_response(session, client, [], verbose=verbose)
                    if full:
                        session.add_assistant(full)
                        cmd_handler.set_last_response(full)
                        prompt_save_code_blocks(full)
                continue

            # /mcp reconnect
            if result.extra.get("mcp_reconnect"):
                with console.status("[dim]MCP 서버 재연결 중...[/dim]"):
                    mcp_manager.disconnect_all()
                    reconnected = mcp_manager.load_and_connect()
                cmd_handler.mcp = mcp_manager
                if reconnected:
                    total_t = sum(len(mcp_manager.servers[s].tools) for s in reconnected)
                    console.print(
                        f"[green]✔ MCP 재연결: {len(reconnected)}개 서버 · {total_t}개 도구[/green]"
                    )
                else:
                    console.print("[yellow]연결된 서버 없음[/yellow]")
                continue

            # /mcp <서버> <도구> 직접 실행
            if result.extra.get("mcp_call"):
                req = result.extra["mcp_call"]
                srv_name, tool_name, tool_args = req["server"], req["tool"], req["args"]
                console.print(
                    f"[dim cyan]⚙ {srv_name} · {tool_name}[/dim cyan]"
                    f"  [dim]{tool_args or ''}[/dim]"
                )
                with console.status(f"[dim]{tool_name} 실행 중...[/dim]"):
                    tool_result = mcp_manager.call_tool(srv_name, tool_name, tool_args)
                console.print(f"\n[dim cyan]gemma[/dim cyan] 도구 실행 결과:\n")
                console.print(tool_result)
                console.print()
                session.add_user(f"[MCP {srv_name}/{tool_name}] 도구 실행 결과:\n{tool_result}")
                session.add_assistant(tool_result)
                cmd_handler.set_last_response(tool_result)
                continue

            # /diff, /commit, /run, /screenshot
            if result.needs_ai and result.ai_prompt:
                extra = result.extra or {}
                img_paths = ([extra["screenshot_path"]] if "screenshot_path" in extra else [])
                session.add_user(result.ai_prompt)
                if not dry_run:
                    full = stream_response(session, client, img_paths, verbose=verbose)
                    if full:
                        session.add_assistant(full)
                        cmd_handler.set_last_response(full)
                        if extra.get("commit_mode"):
                            handle_commit_response(full)
                else:
                    dry_run_preview(result.ai_prompt, [], img_paths, client.model, session)
                continue

            # /profile create
            if result.extra.get("profile_create"):
                pname = result.extra["profile_create"]
                console.print(f"[bold]프로파일 '[cyan]{pname}[/cyan]' 생성[/bold]")
                try:
                    desc       = console.input("  설명: ").strip()
                    sys_prompt = console.input("  시스템 프롬프트: ").strip()
                    mdl        = console.input(f"  모델 [{client.model}]: ").strip() or client.model
                except (EOFError, KeyboardInterrupt):
                    console.print("[yellow]취소됨.[/yellow]")
                    continue
                path = create_profile(pname, {
                    "description": desc, "system_prompt": sys_prompt,
                    "model": mdl, "file_patterns": [], "root_path": None,
                })
                console.print(f"[green]✔ 프로파일 저장: {path}[/green]")
            continue

        # ══════════════════════════════════════════════════════════════
        # 셸 명령어 (! 접두사)
        # ══════════════════════════════════════════════════════════════
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

        # ══════════════════════════════════════════════════════════════
        # 클립보드 이미지 (I-003)
        # ══════════════════════════════════════════════════════════════
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

        # ══════════════════════════════════════════════════════════════
        # @ 파일 참조 파싱
        # ══════════════════════════════════════════════════════════════
        clean_prompt, file_refs, image_refs = parse_at_references(user_input)
        if clipboard_image:
            image_refs.append(clipboard_image)

        context_text  = ""
        valid_images: list[str] = []

        if file_refs or image_refs:
            with console.status("[dim]파일 읽는 중...[/dim]"):
                context_text, valid_images = process_at_references(
                    file_refs, image_refs, client, verbose=verbose
                )

        if valid_images:
            from core.image_handler import image_meta_text
            console.print(image_meta_text(valid_images))

        # ── 최종 메시지 구성 ──────────────────────────────────────────
        if context_text and clean_prompt:
            full_message = f"{context_text}\n\n---\n\n{clean_prompt}"
        elif context_text:
            full_message = f"{context_text}\n\n위 내용을 분석해줘."
        else:
            full_message = user_input

        # ── 토큰 미리보기 ─────────────────────────────────────────────
        show_token_preview(full_message, session, verbose=verbose)

        if dry_run:
            dry_run_preview(full_message, file_refs, image_refs, client.model, session)
            continue

        # ── 자동 모델 라우팅 ──────────────────────────────────────────
        routed_model = select_model(client.model, full_message, bool(valid_images), client)
        if routed_model != client.model and verbose:
            console.print(f"[dim]자동 라우팅: {client.model} → {routed_model}[/dim]")

        session.add_user(full_message)

        # ══════════════════════════════════════════════════════════════
        # AI 응답 — Tool Calling(A) or 스트리밍(B)
        # ══════════════════════════════════════════════════════════════
        use_tools = (
            cmd_handler.mcp_tools_enabled
            and mcp_manager.servers
            and not valid_images
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
            prompt_save_code_blocks(full_response)
            prompt_run_code_blocks(full_response)

    # ── 종료 처리 ─────────────────────────────────────────────────────
    for obs in active_watchers:
        try:
            obs.stop()   # type: ignore[attr-defined]
            obs.join()   # type: ignore[attr-defined]
        except Exception:
            pass

    mcp_manager.disconnect_all()
