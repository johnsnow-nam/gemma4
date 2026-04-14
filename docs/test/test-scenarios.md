---
created: 2026-04-14
status: active
tags: [gemma4, test]
---

# 테스트 시나리오

> 전체 단계별 테스트 가이드: [[../codes/개발현황-및-테스트가이드]]

## 1. Ollama 기본 동작

```bash
# Ollama 서비스 확인
systemctl status ollama

# 모델 목록
ollama list

# 직접 추론 테스트
curl http://localhost:11434/api/generate \
  -d '{"model":"gemma4:e4b","prompt":"hello","stream":false}'
```

기대값: `response` 필드에 텍스트 응답

---

## 2. gemma-cli 테스트

```bash
cd ~/projects/gemma4/gemma-cli
pip install -r requirements.txt
python3 gemma-cli.py

# 터미널에서:
> 안녕하세요            # 기본 대화
> @gemma-cli.py 분석해줘 # 파일 첨부
> /help                 # 커맨드 목록
> /status               # 모델/VRAM 상태
> /clear                # 메모리 초기화
```

---

## 3. gemma-desktop-mcp 테스트

```bash
cd ~/projects/gemma4/gemma-desktop-mcp
pip install fastmcp ollama
python3 gemma-mcp-server.py  # 오류 없이 시작되면 OK
```

Claude Desktop 연동: `claude_desktop_config.json` 설정 후 재시작.

---

## 4. telegram-agent 테스트

```bash
cd ~/projects/gemma4/telegram-agent
pip install -r requirements.txt

# .env 설정
cp .env.example .env
vi .env  # TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID 입력

python3 telegram-agent.py
```

텔레그램에서:
- `/start` — 웰컴 메시지
- `/status` — GPU + Ollama 상태
- `안녕하세요` — AI 답변
- `!ls -la` — 셸 실행
- `빌드해줘` — 현재 프로젝트 빌드
