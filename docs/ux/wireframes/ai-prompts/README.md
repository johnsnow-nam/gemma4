---
created: 2026-04-14
tags: [gemma4, wireframe]
---

# AI 와이어프레임 생성 가이드

> gemma4 프로젝트는 CLI/봇 도구이므로 UI 와이어프레임 대신 UX 플로우 문서를 작성함.

## 주요 인터페이스 UX

### gemma-cli 터미널 UI

```
┌─────────────────────────────────────────────────────────┐
│ gemma4:e4b │ esp32-ocpp │ turn:5 │ 2.1k tokens        │
├─────────────────────────────────────────────────────────┤
│ > @uart.c 메모리 누수 찾아줘_                            │
├─────────────────────────────────────────────────────────┤
│ 분석 중...                                               │
│ `uart.c` 87번 줄에서 `malloc()` 후 `free()` 누락.       │
│                                                          │
│ ```c                                                     │
│ free(buf);  // 추가 필요                                 │
│ ```                                                      │
│                                                          │
│ [s]저장 [r]실행 [n]건너뜀 >                             │
└─────────────────────────────────────────────────────────┘
```

### telegram-agent 대화 흐름

```
Yonghee: 빌드해줘
  Bot:   ⏳ 빌드 중... (ninja -C build)

  Bot:   ❌ 빌드 실패

         uart.c:87: error: undeclared 'buf'

         *AI 분석:*
         buf 변수가 선언되지 않았습니다.
         82번줄 위에 char buf[256]; 를 추가하세요.

Yonghee: uart.c 고쳐줘
  Bot:   ✅ uart.c 수정 완료
         경로: src/uart.c
         백업: src/uart.c.bak

Yonghee: 커밋해줘
  Bot:   ✅ 커밋 완료
         `fix(uart): add missing buf declaration`
```
