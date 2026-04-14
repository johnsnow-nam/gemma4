"""인라인 선택 UI — 화살표 키로 선택, 하단에 표시"""
from __future__ import annotations
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import HTML, merge_formatted_text, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style


_STYLE = Style.from_dict({
    "question":      "bold",
    "selected":      "bg:#00aaaa #ffffff bold",
    "unselected":    "#888888",
    "hint":          "#555555 italic",
    "separator":     "#444444",
})


def select(
    question: str,
    choices: list[tuple[Any, str]],
    default: int = 0,
) -> Any:
    """
    화살표 키 인라인 선택 UI.

    Args:
        question: 질문 문자열
        choices:  [(값, 레이블), ...] 리스트
        default:  기본 선택 인덱스

    Returns:
        선택된 값 (choices[i][0])

    사용 예:
        result = select("파일을 저장할까요?", [
            ("save",   "저장"),
            ("rename", "다른 이름으로"),
            ("skip",   "건너뜀"),
        ])
    """
    idx = [max(0, min(default, len(choices) - 1))]

    def get_content():
        lines = [("class:question", f" {question}\n")]
        for i, (_, label) in enumerate(choices):
            if i == idx[0]:
                lines.append(("class:selected",   f"  ❯ {label}\n"))
            else:
                lines.append(("class:unselected", f"    {label}\n"))
        lines.append(("class:hint", "\n  ↑↓ 이동  Enter 선택  Ctrl+C 취소"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        idx[0] = (idx[0] - 1) % len(choices)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        idx[0] = (idx[0] + 1) % len(choices)

    @kb.add("enter")
    def _enter(event):
        event.app.exit(result=choices[idx[0]][0])

    @kb.add("c-c")
    @kb.add("c-d")
    def _cancel(event):
        event.app.exit(result=None)

    # 숫자키 단축키 (1~9)
    for n in range(1, min(10, len(choices) + 1)):
        @kb.add(str(n))
        def _num(event, n=n):
            if n - 1 < len(choices):
                event.app.exit(result=choices[n - 1][0])

    layout = Layout(
        HSplit([
            Window(
                content=FormattedTextControl(get_content, focusable=True),
                dont_extend_height=True,
            ),
        ])
    )

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        style=_STYLE,
        mouse_support=False,
        full_screen=False,
        refresh_interval=0.05,
    )

    return app.run()


def confirm(question: str, default: bool = False) -> bool:
    """Yes / No 간단 확인창"""
    result = select(
        question,
        [("yes", "Yes"), ("no", "No")],
        default=0 if default else 1,
    )
    return result == "yes"
