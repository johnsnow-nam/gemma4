---
created: 2026-04-14
status: complete
tags: [gemma4, architecture]
---

# 아키텍처 — C4 Context

## Level 1 — System Context

```
┌─────────────────────────────────────────────────────┐
│                   개발자 (Yonghee)                    │
│          터미널 / Claude Desktop / 텔레그램            │
└────────┬────────────┬────────────────┬───────────────┘
         │            │                │
         ▼            ▼                ▼
   [gemma-cli]  [Claude Desktop]  [Telegram App]
   터미널 AI CLI  MCP 도구 호출     스마트폰 봇
         │            │                │
         └────────────┴────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │  Ollama Server   │
            │  localhost:11434 │
            │  gemma4:26b/e4b  │
            └────────┬────────┘
                     │
            ┌────────┴────────┐
            │  Ubuntu Server   │
            │  RTX 5070 12GB   │
            │  CUDA 12.8       │
            └─────────────────┘
```

## Level 2 — Container

```
gemma4 프로젝트
├── gemma-cli (Python 프로세스)
│   ├── prompt_toolkit PromptSession
│   ├── OllamaClient (스트리밍)
│   ├── SlashCommandHandler (25개 커맨드)
│   ├── FileHandler (@참조 파싱)
│   └── Session (대화 메모리)
│
├── gemma-desktop-mcp (FastMCP 서버 프로세스)
│   ├── @mcp.tool() × 12개
│   ├── @mcp.resource() × 2개
│   ├── @mcp.prompt() × 3개
│   └── claude_desktop_config.json 연동
│
└── telegram-agent (Python 프로세스)
    ├── Application (python-telegram-bot)
    ├── TaskExecutor (자연어 디스패처)
    ├── AgentBrain (Ollama 추론)
    ├── FileOps / ShellOps / GitOps
    └── ConversationMemory
```

## Level 3 — Component (telegram-agent 상세)

```
telegram-agent.py
  ├── CommandHandler × 12
  ├── MessageHandler (TEXT → handle_text)
  └── MessageHandler (PHOTO → handle_photo)
        │
        ▼
  TaskExecutor.run(user_input)
        │
   ┌────┴──────────────────────┐
   │ 키워드 매칭 디스패처        │
   │ 빌드 → _handle_build       │
   │ 에러 → _handle_error       │
   │ 수정 → _handle_code_fix    │
   │ 분석 → _handle_file_analysis│
   │ git  → _handle_git         │
   │ !    → _handle_shell       │
   │ else → brain.think()       │
   └────────────────────────────┘
        │
        ▼
  AgentBrain.think() → Ollama API → gemma4
```

## 데이터 흐름

```
사용자 입력 → 키워드 파싱 → 도구 실행 → AI 추론 → 응답 포맷 → 사용자
              (로컬)       (로컬)      (로컬 GPU)  (4096자 제한)
```

모든 처리가 로컬에서 완결됨. 외부 API 호출 없음.
