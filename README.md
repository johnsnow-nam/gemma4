# gemma4

> Gemma4 + Ollama 기반 로컬 AI 개발 도구 모음

Ubuntu 22.04 / RTX 5070 12GB 환경에서 Gemma4 모델을 활용한 AI 에이전트·도구 모음입니다.

---

## 구성 요소

| 폴더 | 설명 | 기술 스택 |
|------|------|-----------|
| `gemma-cli/` | Claude Code 스타일 터미널 AI CLI | Python, Rich, Ollama |
| `gemma-desktop-mcp/` | Claude Desktop / Claude Code MCP 서버 | FastMCP 3.2.4 |
| `citrine-mcp/` | CitrineOS OCPP PostgreSQL MCP 서버 | psycopg2, FastMCP |
| `telegram-agent/` | Telegram 봇 AI 에이전트 | python-telegram-bot 22.7 |
| `system-monitor/` | 시스템 실시간 대시보드 | FastAPI, WebSocket |
| `buddy-mcp/` | Bluetooth 마이크로컨트롤러 MCP 서버 | pyserial, MCP |
| `scripts/` | Ollama / OpenWebUI 설치 스크립트 | Bash |
| `docs/` | 설계 문서 및 보안 감사 보고서 | Markdown |
| `refs/` | 레퍼런스 라이브러리·예제 관리 | git submodule |

---

## 시스템 구성도

```
┌─────────────────────────────────────────────────────────┐
│                      사용자 인터페이스                     │
│   gemma-cli (터미널)  │  Telegram Bot  │  Claude Desktop  │
└──────────────┬────────┴───────┬────────┴────────┬────────┘
               │                │                 │
               ▼                ▼                 ▼
┌──────────────────────────────────────────────────────────┐
│                     MCP 서버 레이어                        │
│  gemma-desktop-mcp  │  citrine-mcp  │  buddy-mcp         │
└──────────────┬───────┴──────┬────────┴────────┬──────────┘
               │              │                 │
               ▼              ▼                 ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
│  Ollama (로컬)   │  │  CitrineOS   │  │  마이크로컨트롤러  │
│  gemma4:26b      │  │  PostgreSQL  │  │  (Bluetooth)      │
│  gemma4:e4b      │  │  OCPP DB     │  │  DC모터·서보·IO   │
└──────────────────┘  └──────────────┘  └──────────────────┘
```

---

## 환경 요구사항

- **OS**: Ubuntu 22.04
- **GPU**: RTX 5070 12GB (VRAM)
- **Python**: 3.10+
- **Ollama**: 최신 버전
- **모델**: gemma4:26b (고성능), gemma4:e4b (경량)

---

## 빠른 시작

### Ollama 모델 설치

```bash
ollama pull gemma4:26b
ollama pull gemma4:e4b
```

### gemma-cli 실행

```bash
cd gemma-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python gemma-cli.py
```

### Claude Code MCP 서버 연결 확인

```bash
claude mcp list
```

```
gemma4-local:    ✓ Connected   # Gemma4 로컬 AI + 파일시스템
citrine-ocpp-db: ✓ Connected   # CitrineOS OCPP PostgreSQL
```

### Telegram 에이전트 상태 확인

```bash
systemctl status telegram-agent
```

### 시스템 모니터 실행

```bash
system-monitor   # http://localhost:9090
```

---

## MCP 서버 목록

| 서버명 | 도구 수 | 용도 |
|--------|---------|------|
| `gemma4-local` | 12 | Gemma4 AI 추론 + 파일/Git/셸 |
| `citrine-ocpp-db` | 9 | CitrineOS OCPP DB 조회 |
| `buddy-mcp` | 7 | Bluetooth 보드 제어 |

---

## buddy-mcp (서브모듈)

Bluetooth 직렬 통신으로 마이크로컨트롤러 보드를 제어하는 MCP 서버입니다.

```bash
cd buddy-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 설정 출력
python3 run.py --print-mcp-config
```

> 하드웨어(Bluetooth 동글 + 호환 보드) 연결 시에만 동작합니다.

---

## 보안

- Telegram 봇: `ALLOWED_USER_IDS` 로 허가된 사용자만 접근
- MCP 서버: 로컬 전용 (`127.0.0.1` 바인딩)
- 환경변수: `.env` 파일 권한 `600`
- 보안 감사 보고서: `docs/seokhee/security-report.md`

---

## 서브모듈 초기화

이 저장소를 클론한 경우:

```bash
git clone https://github.com/johnsnow-nam/gemma4.git
cd gemma4
git submodule update --init --recursive
```
