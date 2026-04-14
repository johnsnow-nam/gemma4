"""MCP 클라이언트 — stdio 기반 MCP 서버 연결 및 도구 호출"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

# ─── MCP 서버 설정 ────────────────────────────────────────────────────────────
CLAUDE_JSON = Path.home() / ".claude.json"


def _load_server_configs() -> dict[str, dict]:
    """~/.claude.json 에서 MCP 서버 설정 로드"""
    if not CLAUDE_JSON.exists():
        return {}
    try:
        data = json.loads(CLAUDE_JSON.read_text())
        return data.get("mcpServers", {})
    except Exception:
        return {}


# ─── 경량 MCP stdio 클라이언트 ────────────────────────────────────────────────

class MCPServer:
    """단일 MCP 서버와 통신하는 클라이언트"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._proc: subprocess.Popen | None = None
        self._req_id = 0
        self.tools: list[dict] = []
        self.connected = False

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send(self, method: str, params: dict | None = None) -> dict | None:
        """JSON-RPC 요청 전송 후 응답 반환"""
        if self._proc is None:
            return None

        msg = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            msg["params"] = params

        try:
            line = json.dumps(msg) + "\n"
            self._proc.stdin.write(line.encode())
            self._proc.stdin.flush()

            # 응답 읽기 (알림 메시지는 건너뜀)
            for _ in range(20):
                raw = self._proc.stdout.readline()
                if not raw:
                    break
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    resp = json.loads(raw)
                    if "id" in resp and resp["id"] == msg["id"]:
                        return resp
                    # id 없는 알림은 무시
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return None

    def _send_notification(self, method: str, params: dict | None = None) -> None:
        """응답 없는 알림 메시지 전송"""
        if self._proc is None:
            return
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        try:
            self._proc.stdin.write((json.dumps(msg) + "\n").encode())
            self._proc.stdin.flush()
        except Exception:
            pass

    def connect(self) -> bool:
        """서버 프로세스 시작 및 초기화"""
        try:
            cmd = self.config.get("command", "")
            args = self.config.get("args", [])
            env = {**os.environ, **self.config.get("env", {})}

            self._proc = subprocess.Popen(
                [cmd] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
            )

            # initialize
            resp = self._send("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gemma-cli", "version": "1.0"},
            })
            if not resp or "error" in resp:
                self.disconnect()
                return False

            # initialized 알림
            self._send_notification("notifications/initialized")

            # 도구 목록
            tools_resp = self._send("tools/list")
            if tools_resp and "result" in tools_resp:
                self.tools = tools_resp["result"].get("tools", [])

            self.connected = True
            return True

        except Exception:
            self.disconnect()
            return False

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> str:
        """도구 호출 — 결과를 문자열로 반환"""
        if not self.connected or self._proc is None:
            return f"❌ 서버 '{self.name}' 에 연결되지 않았습니다."

        resp = self._send("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })

        if resp is None:
            return "❌ 응답 없음 (타임아웃)"
        if "error" in resp:
            err = resp["error"]
            return f"❌ 오류: {err.get('message', str(err))}"

        result = resp.get("result", {})
        content = result.get("content", [])

        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))

        return "\n".join(parts) if parts else "(빈 응답)"

    def disconnect(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self.connected = False


# ─── 멀티 서버 매니저 ─────────────────────────────────────────────────────────

class MCPManager:
    """여러 MCP 서버를 통합 관리"""

    def __init__(self):
        self._servers: dict[str, MCPServer] = {}

    def load_and_connect(self) -> list[str]:
        """~/.claude.json 에서 서버 로드 후 연결. 성공한 서버 이름 목록 반환"""
        configs = _load_server_configs()
        connected = []
        for name, cfg in configs.items():
            srv = MCPServer(name, cfg)
            if srv.connect():
                self._servers[name] = srv
                connected.append(name)
        return connected

    def reconnect(self, name: str) -> bool:
        """특정 서버 재연결"""
        configs = _load_server_configs()
        if name not in configs:
            return False
        srv = MCPServer(name, configs[name])
        if name in self._servers:
            self._servers[name].disconnect()
        if srv.connect():
            self._servers[name] = srv
            return True
        return False

    @property
    def servers(self) -> dict[str, MCPServer]:
        return self._servers

    def all_tools(self) -> list[tuple[str, dict]]:
        """(서버명, 도구정보) 전체 목록"""
        result = []
        for srv_name, srv in self._servers.items():
            for tool in srv.tools:
                result.append((srv_name, tool))
        return result

    def find_tool(self, tool_name: str) -> tuple[str, MCPServer] | None:
        """도구 이름으로 서버 탐색"""
        for srv_name, srv in self._servers.items():
            for tool in srv.tools:
                if tool["name"] == tool_name:
                    return srv_name, srv
        return None

    def call_tool(self, server_name: str, tool_name: str,
                  arguments: dict | None = None) -> str:
        """서버+도구명으로 직접 호출"""
        if server_name not in self._servers:
            return f"❌ 서버를 찾을 수 없습니다: {server_name}"
        return self._servers[server_name].call_tool(tool_name, arguments)

    def to_ollama_tools(self) -> list[dict]:
        """MCP 도구 목록을 Ollama tool calling 형식으로 변환"""
        ollama_tools = []
        for srv_name, tool in self.all_tools():
            schema = tool.get("inputSchema", {})
            props = schema.get("properties", {})
            required = schema.get("required", [])

            # Ollama tool 형식
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": (
                        f"[{srv_name}] {tool.get('description', '')}"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            })
        return ollama_tools

    def execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Ollama tool_calls 를 실행하고 tool 역할 메시지 목록 반환"""
        messages = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}

            # 서버 찾아서 실행
            found = self.find_tool(name)
            if found:
                _, srv = found
                result = srv.call_tool(name, args)
            else:
                result = f"❌ 도구를 찾을 수 없습니다: {name}"

            messages.append({
                "role": "tool",
                "content": result,
            })
        return messages

    def disconnect_all(self) -> None:
        for srv in self._servers.values():
            srv.disconnect()
        self._servers.clear()

    def status_text(self) -> str:
        """연결 상태 텍스트"""
        if not self._servers:
            return "연결된 MCP 서버 없음"
        lines = []
        for name, srv in self._servers.items():
            icon = "✅" if srv.connected else "❌"
            lines.append(f"{icon} {name} ({len(srv.tools)}개 도구)")
        return "\n".join(lines)
