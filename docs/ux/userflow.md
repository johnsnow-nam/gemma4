---
created: 2026-04-14
status: complete
tags: [gemma4, ux, userflow]
---

# 사용자 플로우

## gemma-cli 플로우

```
시작
  └─► python3 gemma-cli.py [--model] [--profile] [--dry-run]
        │
        ├─► 상태바 표시 (모델 / 프로젝트 / 턴 수 / 토큰)
        │
        ├─► 입력 대기 (Tab 자동완성 지원)
        │     │
        │     ├─ "!" 입력 → 셸 직접 실행
        │     ├─ "/" 입력 → 슬래시 커맨드 목록
        │     │     ├─ /help, /status, /model, /profile
        │     │     ├─ /save, /load, /sessions
        │     │     ├─ /clear, /compress
        │     │     ├─ /watch <파일>, /commit, /diff
        │     │     └─ /run, /save-code
        │     │
        │     ├─ "@파일" 입력 → 파일 내용 컨텍스트 주입
        │     └─ 일반 텍스트 → AI 추론 → 스트리밍 출력
        │
        └─► Ctrl+D → 종료
```

## telegram-agent 플로우

```
Telegram 앱
  └─► /start → 웰컴 + 현재 프로젝트 안내
        │
        ├─► /status    → GPU / Ollama / 모델 상태
        ├─► /projects  → 프로젝트 목록 (▶ 현재 프로젝트 표시)
        ├─► /project X → 프로젝트 전환
        ├─► /model X   → 모델 변경
        ├─► /build     → 빌드 실행
        ├─► /diff      → git diff
        ├─► /commit    → 자동 커밋
        ├─► /tree      → 폴더 트리
        ├─► /clear     → 메모리 초기화
        └─► /save      → 세션 저장

일반 메시지:
  텍스트 → TaskExecutor.run() → 키워드 분석 → 작업 실행 → 답변
  이미지 → AgentBrain.think_with_image() → 비전 분석 → 답변
```
