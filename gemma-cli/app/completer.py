"""Tab 자동완성 — 슬래시 명령어 + @ 파일 경로"""
from __future__ import annotations

import os

from prompt_toolkit.completion import Completer, Completion

SLASH_COMMANDS = [
    "/help", "/clear", "/retry", "/compress", "/copy", "/copy code",
    "/save", "/load", "/sessions", "/model", "/models", "/set",
    "/profile", "/profiles", "/run", "/watch", "/diff", "/commit",
    "/screenshot", "/ls", "/tokens", "/config", "/verbose", "/exit", "/quit",
    "/mcp", "/mcp list", "/mcp status", "/mcp reconnect", "/mcp tools",
]


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
