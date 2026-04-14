---
created: 2026-04-14
status: complete
tags: [gemma4, planning, user-journey]
---

# 사용자 여정

## 여정 1 — 처음 설치하는 개발자

```
1. README 확인
2. Ollama 설치 (scripts/install_ollama.sh)
3. 모델 다운로드: ollama pull gemma4:26b
4. 도구 선택:
   - 터미널 작업 → gemma-cli 설치 (pip install -r requirements.txt)
   - Claude Desktop 사용자 → gemma-desktop-mcp/install.sh
   - 원격 작업 → telegram-agent/install.sh + .env 설정
5. 첫 실행 및 /start or /help
```

## 여정 2 — 일상 개발 루틴

```
아침:
  → gemma-cli 실행
  → 어제 작업 맥락 로드 (/load)
  → 오늘 빌드 상태 확인 (@CMakeLists.txt 분석해줘)

작업 중:
  → @파일명으로 코드 첨부 → AI 리뷰
  → /watch uart.c 로 실시간 피드백
  → 수정 완료 후 /commit

외출 중:
  → 텔레그램 봇으로 빌드 상태 확인
  → "에러 고쳐줘" 메시지로 원격 수정
```

## 여정 3 — 문제 발생 시

```
빌드 실패:
  → gemma-cli: 에러 로그 @붙여넣기 → 분석
  → telegram-agent: 자동 AI 에러 분석 전송

이해 안 되는 코드:
  → gemma-cli: @ocpp_handler.c "이 함수 설명해줘"
  → Claude Desktop: read_file + ask_gemma 조합
```
