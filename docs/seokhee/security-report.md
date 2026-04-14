# 보안 감사 보고서
- **날짜**: 2026-04-14
- **시스템**: Gemma4 AI 에이전트 시스템 (gemma-cli / gemma-desktop-mcp / telegram-agent / system-monitor)
- **점검자**: Claude Code

---

## 요약

| 구분 | 수 |
|---|---|
| 전체 점검 항목 | 24개 |
| ✅ 안전 | 11개 |
| ⚠️ 경고 (수정 권장) | 9개 |
| ❌ 심각 (즉시 수정) | 1개 |
| 🔧 수정 완료 | 4개 |

---

## 수정 완료 항목 (이번 점검에서 즉시 수정)

| 항목 | 내용 | 조치 |
|---|---|---|
| SEC-001 | `.env` 권한 664 → **600** 수정 | `chmod 600 telegram-agent/.env` |
| SEC-015 | `.env` 타인 읽기 가능 → **차단** | 동일 |
| SEC-017 | `claude_desktop_config.json` 권한 664 → **600** 수정 | `chmod 600` |
| SEC-005/022 | System Monitor `0.0.0.0:9090` → **127.0.0.1** 바인딩 수정 | `monitor.py` host 수정 후 재시작 |

---

## 발견된 취약점 상세

### ❌ 심각 (즉시 수정 필요)

| 항목 | 내용 | 수정 방법 |
|---|---|---|
| SEC-003 | **Bot Token이 systemd 로그에 URL로 노출** | httpx 로그 레벨 낮추기 또는 로그 필터 추가 |

```
# 로그에 노출되는 패턴:
POST https://api.telegram.org/botREDACTED_BOT_TOKEN/getUpdates
```

**수정 방법** — `telegram-agent.py` logging 설정 수정:
```python
# httpx 로그 레벨을 WARNING으로 올려서 URL 노출 차단
logging.getLogger("httpx").setLevel(logging.WARNING)
```

---

### ⚠️ 경고 (수정 권장)

| 항목 | 내용 | 현재 상태 | 권장 조치 |
|---|---|---|---|
| SEC-006 | UFW 방화벽 미활성화 | 비활성 | `sudo ufw enable` + 포트 규칙 |
| SEC-010 | `gemma-desktop-mcp/tools/shell_tool.py` `shell=True` 사용 | 위험 패턴 차단 있음 | 파이프 명령어 지원 필요 시 허용, 단 차단 목록 강화 |
| SEC-012 | telegram-agent 파일 경로 제한 없음 (`../` 탐색 가능) | 미구현 | `realpath` 기반 화이트리스트 추가 |
| SEC-013 | System Monitor 인증 없음 | 미구현 | Basic Auth 또는 로컬 전용 접근 유지 |
| SEC-014 | sudoers 권한 과도 (`/bin/systemctl start *`) | 전체 서비스 허용 | 특정 서비스만 명시 |
| SEC-021 | Ubuntu 보안 업데이트 미확인 | 미점검 | `sudo apt upgrade` 실행 |
| SEC-023 | SSH PasswordAuthentication 설정 미확인 | 미점검 | 키 인증만 허용 권장 |
| SEC-024 | fail2ban 미설치 | 미설치 | `sudo apt install fail2ban` |

---

### ✅ 안전 항목

| 항목 | 내용 |
|---|---|
| SEC-002 | `.env` Git 히스토리 없음, `.gitignore`에 `.env` 등록됨 |
| SEC-004 | systemd `EnvironmentFile` 방식 사용 — 프로세스 목록에 토큰 미노출 |
| SEC-007 | Ollama `127.0.0.1:11434` 로컬 전용 바인딩 ✅ |
| SEC-008 | Open WebUI 인증 활성화 상태 |
| SEC-009 | `ALLOWED_USER_IDS=5634282715` 설정됨 — 인가된 사용자만 접근 |
| SEC-011 | BLOCKED_COMMANDS 목록 구현됨 |
| SEC-016 | systemd 서비스 파일 root 소유, 644 권한 |
| SEC-018 | MCP 서버 일반 사용자(`caram88`) 권한으로 실행 |
| SEC-019 | Ollama 모델 3종 정상 등록 (gemma4:26b/e2b/e4b) |

---

## 즉시 실행 권장 명령어 (터미널에서 직접)

### 1. Bot Token 로그 노출 수정 (SEC-003)
이미 코드 수정 후 telegram-agent 재시작 필요.

### 2. UFW 방화벽 활성화 (SEC-006)
```bash
sudo ufw enable
sudo ufw allow 22        # SSH
sudo ufw deny 8080       # Open WebUI 외부 차단
sudo ufw deny 11434      # Ollama 외부 차단
sudo ufw status verbose
```

### 3. sudoers 최소 권한 (SEC-014)
```bash
sudo visudo -f /etc/sudoers.d/ai-monitor-control
# 내용을 아래로 교체:
# caram88 ALL=(ALL) NOPASSWD: /bin/systemctl start ollama, /bin/systemctl stop ollama, /bin/systemctl restart ollama, /bin/systemctl start open-webui, /bin/systemctl stop open-webui, /bin/systemctl restart open-webui, /bin/systemctl start telegram-agent, /bin/systemctl stop telegram-agent, /bin/systemctl restart telegram-agent
```

### 4. fail2ban 설치 (SEC-024)
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 5. Ubuntu 보안 업데이트 (SEC-021)
```bash
sudo apt update && sudo apt upgrade -y
```

---

## 잔여 권장 조치 (이번 주 내)

- [ ] SEC-003: httpx 로그에서 토큰 URL 마스킹
- [ ] SEC-006: UFW 방화벽 활성화
- [ ] SEC-012: telegram-agent 파일 경로 화이트리스트
- [ ] SEC-013: System Monitor Basic Auth 추가
- [ ] SEC-014: sudoers 최소 권한으로 교체
- [ ] SEC-021: Ubuntu 보안 업데이트
- [ ] SEC-024: fail2ban 설치

---

*보고서 생성: Claude Code · 2026-04-14*
