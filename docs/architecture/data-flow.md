---
created: 2026-04-14
status: complete
tags: [gemma4, architecture, data-flow]
---

# 데이터 흐름

## gemma-cli 흐름

```
사용자 입력 (prompt_toolkit)
  │
  ├── "!" 접두사 → ShellCommand 직접 실행
  ├── "/" 접두사 → SlashCommandHandler 라우팅
  ├── "@파일명"  → FileHandler.parse_at_references() → 파일 내용 컨텍스트 주입
  └── 일반 텍스트 → OllamaClient.chat_stream()
                          │
                    Ollama HTTP API (localhost:11434)
                          │
                    gemma4 모델 추론 (GPU)
                          │
                    Rich Live 스트리밍 출력
                          │
                    Session.add_assistant() (메모리 저장)
```

## gemma-desktop-mcp 흐름

```
Claude Desktop (사용자 메시지)
  │
  MCP 프로토콜 (stdio)
  │
  FastMCP 서버 (gemma-mcp-server.py)
  │
  ├── 파일 도구: read_file, write_file (홈 디렉토리 보안 검사)
  ├── 셸 도구: run_shell (위험 명령어 패턴 차단)
  ├── AI 도구: ask_gemma → OllamaClient → gemma4
  └── Git 도구: git_status/diff/commit (subprocess)
  │
  Claude Desktop (결과 표시)
```

## telegram-agent 흐름

```
Telegram 서버 (polling)
  │
  Update 수신
  │
  auth_check (ALLOWED_USER_ID 검증)
  │
  ├── 커맨드(/start 등) → CommandHandler
  ├── 텍스트 → TaskExecutor.run()
  │               │
  │         키워드 분석 → 작업 선택
  │               │
  │         FileOps/ShellOps/GitOps 실행
  │               │
  │         AgentBrain.think() → Ollama
  │               │
  │         _truncate(4000자) → 응답
  └── 이미지 → AgentBrain.think_with_image()
                    │
              base64 인코딩 → Ollama vision API
                    │
              Telegram 답장 (4096자 분할)
```

## 보안 경계

| 도구 | 차단 내용 |
|------|-----------|
| ShellOps | BLOCKED_COMMANDS 목록, sudo 접두사 |
| FileOps (MCP) | 홈 디렉토리 외 쓰기 금지 (/etc, /usr, /sys, /proc) |
| telegram-agent | ALLOWED_USER_ID 인증, 차단 명령어 목록 |
