"""Phase A: Tool Calling 루프 — Gemma ↔ MCP 자동 도구 호출"""
from __future__ import annotations

from rich.console import Console

from ui.response import stream_response

console = Console()

MAX_TOOL_ROUNDS = 5  # 무한 루프 방지


def run_with_tools(
    session,
    client,
    mcp_manager,
    verbose: bool = False,
) -> str:
    """Tool Calling 루프:
    1. Gemma 호출 (tools 포함)
    2. tool_calls 있으면 → MCP 실행 → 결과 추가 → 반복
    3. 최종 텍스트 응답 반환
    """
    tools = mcp_manager.to_ollama_tools()
    if not tools:
        return stream_response(session, client, [], verbose=verbose)

    full_response = ""

    for round_num in range(MAX_TOOL_ROUNDS):
        if verbose:
            console.print(f"[dim]Tool round {round_num + 1}/{MAX_TOOL_ROUNDS}[/dim]")

        try:
            text, tool_calls = client.chat_with_tools(session.messages, tools)
        except Exception as e:
            console.print(f"[red]Tool Calling 오류: {e}[/red]")
            return stream_response(session, client, [], verbose=verbose)

        # 도구 호출 없음 → 최종 응답
        if not tool_calls:
            if text:
                console.print()
                console.print("[dim cyan]gemma[/dim cyan] ", end="")
                console.print(text, markup=False)
                console.print()
            full_response = text
            break

        # 어시스턴트 메시지 저장 (tool_calls 포함)
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
            console.print(
                f"\n[dim cyan]⚙ MCP 도구 호출:[/dim cyan] [cyan]{name}[/cyan]",
                end="",
            )
            if args:
                console.print(f"  [dim]{args}[/dim]", end="")
            console.print()

        tool_messages = mcp_manager.execute_tool_calls(tool_calls)
        for msg in tool_messages:
            preview = msg["content"][:200]
            console.print(
                f"[dim]  → {preview}"
                f"{'...' if len(msg['content']) > 200 else ''}[/dim]"
            )
            session.messages.append(msg)

    return full_response
