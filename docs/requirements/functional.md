---
created: 2026-04-14
status: complete
tags: [gemma4, requirements, functional]
---

# 기능 요구사항

## gemma-cli

| ID | 기능 | 구현 |
|----|------|------|
| F-001 | Ollama 스트리밍 응답 (Rich Live) | ✅ |
| F-002 | `@파일명` 파일 컨텍스트 첨부 | ✅ |
| F-003 | `@폴더/` 폴더 요약 첨부 | ✅ |
| F-004 | 이미지 첨부 (로컬 파일, 클립보드, 스크린샷) | ✅ |
| F-005 | `/watch` 파일 변경 감지 자동 분석 | ✅ |
| F-006 | 응답 코드블록 파일 저장 | ✅ |
| C-001 | 25개 슬래시 커맨드 | ✅ |
| C-002 | 코드블록 실행 (`/run`) | ✅ |
| M-003 | 자동 모델 라우팅 (입력 길이/이미지 기준) | ✅ |
| G-003 | AI 자동 커밋 메시지 생성 | ✅ |
| D-005 | 세션 압축 (토큰 절약) | ✅ |
| V-002 | dry-run 모드 (파일 변경 미리보기) | ✅ |

## gemma-desktop-mcp

| ID | 기능 | 구현 |
|----|------|------|
| MCP-001 | `ask_gemma` — 기본 AI 질문 | ✅ |
| MCP-002 | `ask_gemma_with_files` — 파일 포함 질문 | ✅ |
| MCP-003 | `read_file` — 파일 읽기 | ✅ |
| MCP-004 | `write_file` — 파일 쓰기 (홈 디렉토리 보안) | ✅ |
| MCP-005 | `read_folder` — 폴더 요약 | ✅ |
| MCP-006 | `run_shell` — 셸 실행 (위험 명령어 차단) | ✅ |
| MCP-007 | `git_status/diff/commit` — Git 연동 | ✅ |
| MCP-008 | `analyze_image` — 이미지 비전 분석 | ✅ |
| MCP-009 | `search_files` — 파일 내용 검색 | ✅ |
| MCP-010 | `get_system_info` — GPU/시스템 상태 | ✅ |

## telegram-agent

| ID | 기능 | 구현 |
|----|------|------|
| BOT-001 | 12개 슬래시 커맨드 | ✅ |
| EXEC-001 | 자연어 → 작업 디스패처 | ✅ |
| BRAIN-001 | Gemma4 Ollama 추론 + 이미지 비전 | ✅ |
| FILE-001 | 파일 읽기/쓰기/검색/백업 | ✅ |
| SHELL-001 | 비동기 셸 실행 (차단 목록 보안) | ✅ |
| GIT-001 | Git status/diff/commit | ✅ |
| MEM-001 | 대화 세션 메모리 저장/로드 | ✅ |
