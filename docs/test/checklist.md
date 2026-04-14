---
created: 2026-04-14
status: active
tags: [gemma4, test, checklist]
---

# 테스트 체크리스트

## Ollama 환경
- [ ] `ollama list` 에 gemma4:26b 또는 gemma4:e4b 표시
- [ ] `curl localhost:11434/api/tags` 응답 정상
- [ ] nvidia-smi 에서 VRAM 여유 확인

## gemma-cli
- [ ] `python3 gemma-cli.py` 실행 후 프롬프트 표시
- [ ] 기본 대화 응답
- [ ] `@파일명` 파일 첨부 동작
- [ ] `/help` 커맨드 목록 출력
- [ ] `/status` GPU/모델 정보 출력
- [ ] 코드블록 응답 시 저장 여부 질문
- [ ] `/commit` AI 커밋 메시지 생성

## gemma-desktop-mcp
- [ ] `python3 gemma-mcp-server.py` 오류 없이 시작
- [ ] `install.sh` 실행 후 claude_desktop_config.json 업데이트
- [ ] Claude Desktop 재시작 후 MCP 도구 목록 표시
- [ ] `ask_gemma` 도구 동작

## telegram-agent
- [ ] `.env` 파일 TELEGRAM_BOT_TOKEN 설정
- [ ] `python3 telegram-agent.py` 오류 없이 시작
- [ ] `/start` 응답
- [ ] `/status` GPU + Ollama 상태 표시
- [ ] 일반 텍스트 → AI 답변
- [ ] `!ls` 셸 실행 결과 반환
- [ ] 이미지 전송 → 비전 분석 응답
- [ ] `빌드해줘` → 현재 프로젝트 빌드 실행
