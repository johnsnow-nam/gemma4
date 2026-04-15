---
project: gemma4
created: 2026-04-14
status: active
---

# gemma4

## 개요
- 설명: Gemma4 + Ollama 기반 로컬 AI 개발 도구 모음
- 환경: Ubuntu 22.04 / RTX 5070 12GB / Python 3.10 / Ollama
- 주요 모델: gemma4:26b (고성능), gemma4:e4b (경량)

## 구성 요소
- `gemma-cli/` — Claude Code 스타일 터미널 AI (Rich + prompt_toolkit)
- `gemma-desktop-mcp/` — Claude Desktop MCP 서버 (FastMCP 3.2.4)
- `telegram-agent/` — Telegram 봇 AI 에이전트 (python-telegram-bot 22.7)
- `scripts/` — Ollama/OpenWebUI 설치, OCPP fine-tuning

## 문서 위치
- 작업일지: /home/caram88/ws-obsidian/Projects/gemma4/
- 요구사항: docs/requirements/README.md
- 기획: docs/planning/business-analysis.md
- 아키텍처: docs/architecture/c4-context.md
- 테스트 가이드: docs/codes/개발현황-및-테스트가이드.md

## 최근 현황
- 2026-04-14: gemma-cli / gemma-desktop-mcp / telegram-agent 전체 구현 완료

## 다음 할 일
- [x] telegram-agent 실기기 연결 테스트
- [x] gemma-cli esp32-ocpp 프로젝트 실사용 검증
- [x] Claude Desktop MCP 연결 검증
