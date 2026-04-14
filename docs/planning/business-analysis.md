---
created: 2026-04-14
status: complete
tags: [gemma4, planning]
---

# 비즈니스 분석

## 배경 및 목적

RTX 5070 12GB VRAM을 탑재한 로컬 서버에서 Gemma4를 무료로 실행할 수 있는 환경이 구축됨.
Claude API 비용 없이, 민감한 코드를 외부에 보내지 않고, 로컬에서 AI 개발 지원 도구를 구성하는 것이 목표.

## 핵심 가치

| 가치 | 설명 |
|------|------|
| 무료 | Ollama + 로컬 모델, API 비용 없음 |
| 보안 | 코드가 외부 서버로 전송되지 않음 |
| 속도 | 로컬 GPU 추론, 네트워크 지연 없음 |
| 커스텀 | 도메인 특화 fine-tuning 가능 (OCPP) |

## 사용 시나리오

### 시나리오 1 — 터미널 개발 (gemma-cli)
```
개발자 → 터미널에서 gemma-cli 실행
→ @uart.c 첨부 → "메모리 누수 찾아줘"
→ AI 분석 → 코드 수정안 제안
→ /save 로 파일 저장 → /run 으로 검증
→ /commit 으로 자동 커밋
```

### 시나리오 2 — Claude Desktop 연동 (gemma-desktop-mcp)
```
개발자 → Claude Desktop 채팅창
→ "esp32-ocpp 프로젝트 빌드 에러 분석해줘"
→ MCP: read_folder → run_shell(ninja -C build) → ask_gemma
→ Claude: 에러 원인과 수정 방법 제시
```

### 시나리오 3 — 원격 작업 (telegram-agent)
```
개발자 (외출 중, 스마트폰)
→ 텔레그램: "빌드해줘"
→ 서버: ninja 실행 → 실패 → Gemma4 에러 분석
→ 텔레그램: "❌ 빌드 실패 / 원인: xxx / 수정: uart.c 87번줄"
→ "uart.c 고쳐줘" → 파일 수정 + 커밋
→ "다시 빌드해줘" → "✅ 빌드 성공"
```

## 향후 계획

- OCPP 도메인 fine-tuning (ocpp_finetune.py 준비됨)
- 빌드 실패 시 자동 알림 (cron + telegram push)
- 멀티 프로젝트 동시 관리
