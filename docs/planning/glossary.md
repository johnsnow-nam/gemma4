---
created: 2026-04-14
tags: [gemma4, glossary]
---

# 용어 사전

프로젝트에서 사용하는 핵심 용어 정의.
Claude가 일관된 이해를 위해 이 파일을 참고함.

| 용어 | 정의 |
|------|------|
| Ollama | 로컬에서 LLM을 실행하는 런타임. `localhost:11434` 에서 동작 |
| Gemma4 | Google의 멀티모달 LLM. gemma4:26b (고성능), gemma4:e4b (경량), gemma4:e2b (초경량) |
| MCP | Model Context Protocol. Claude Desktop이 외부 도구를 호출하는 표준 프로토콜 |
| FastMCP | Python MCP 서버 프레임워크 (v3.2.4). `@mcp.tool()` 데코레이터로 도구 등록 |
| gemma-cli | 이 프로젝트의 터미널 AI CLI. `gemma-cli/gemma-cli.py` |
| gemma-desktop-mcp | Claude Desktop용 MCP 서버. `gemma-desktop-mcp/gemma-mcp-server.py` |
| telegram-agent | Telegram 봇 AI 에이전트. `telegram-agent/telegram-agent.py` |
| OCPP | Open Charge Point Protocol 1.6. ESP32 충전기 펌웨어의 통신 프로토콜 |
| esp32-ocpp | Yonghee의 ESP32 OCPP 1.6 충전기 펌웨어 프로젝트 |
| TaskExecutor | telegram-agent의 자연어 명령 디스패처 클래스 |
| AgentBrain | Ollama 추론 엔진 클래스 (gemma-cli의 OllamaClient와 대응) |
| .claudeignore | Claude가 읽지 않을 파일/폴더 목록 (daily/, *.log 등) |
| dry-run | 실제 파일 변경 없이 변경 사항을 미리 보여주는 모드 |
| Conventional Commits | `feat:`, `fix:`, `chore:` 등 커밋 메시지 표준 형식 |
