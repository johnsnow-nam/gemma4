# 보안 감사 작업 지침서
> Gemma4 + Ollama + Telegram Bot + Open WebUI + System Monitor 통합 보안 점검
> 작성일: 2026-04-14
> Claude Code에게 전달하는 보안 감사 명세서

---

## 개발 현황 범례

| 기호 | 의미 |
|---|---|
| ✅ | 점검 완료 / 안전 |
| ⚠️ | 취약점 발견 / 수정 필요 |
| ❌ | 심각한 취약점 |
| ⬜ | 미점검 |

---

## 1. 보안 점검 개요

### 1.1 점검 대상 시스템
```
1. Telegram Bot    — seokhee_gemma_bot (telegram-agent.py)
2. Ollama          — localhost:11434
3. Open WebUI      — localhost:8080
4. System Monitor  — localhost:9090
5. Gemma MCP 서버  — stdio 프로세스
6. Ubuntu 시스템   — 방화벽, 포트, 파일 권한
7. 환경변수 / .env — 시크릿 관리
```

### 1.2 위협 모델
```
외부 공격자
  → 오픈 포트 스캔 → Ollama/WebUI 무단 접근
  → 텔레그램 봇 탈취 → 서버 명령 실행

내부 취약점
  → .env 토큰 노출
  → 셸 명령어 인젝션
  → 과도한 파일 권한
  → 로그에 시크릿 노출
```

---

## 2. Claude Code 실행 명령

```bash
cd ~/security-audit
claude

# Claude Code에게 입력:
"security-audit-spec.md 파일을 읽고
 모든 보안 점검 항목을 순서대로 실행해줘.

 점검 방법:
 1. 각 항목별 실제 명령어 실행
 2. 결과 분석 후 취약점 판단
 3. 취약점 발견 시 즉시 수정 코드 제시
 4. 점검 완료 항목은 ⬜ → ✅/⚠️/❌ 로 업데이트
 5. 최종 보안 보고서 security-report.md 생성

 점검 대상 경로:
 - ~/projects/gemma4/telegram-agent/
 - ~/.config/Claude/claude_desktop_config.json
 - /etc/systemd/system/telegram-agent.service
 - /etc/systemd/system/open-webui.service
 - /etc/systemd/system/system-monitor.service"
```

---

## 3. 보안 점검 항목

---

### 3.1 시크릿 / 자격증명 관리

#### ✅ SEC-001: .env 파일 권한 확인
> 점검일: 2026-04-14 | 결과: 664(위험) → **600으로 수정 완료** | `chmod 600 telegram-agent/.env`
```bash
# 실행할 명령어
stat ~/projects/gemma4/telegram-agent/.env
ls -la ~/projects/gemma4/telegram-agent/.env

# 정상: -rw------- (600) — 본인만 읽기
# 위험: -rw-r--r-- (644) — 다른 사용자도 읽기 가능

# 수정 명령어 (취약 시)
chmod 600 ~/projects/gemma4/telegram-agent/.env
```

#### ✅ SEC-002: .env 파일 내용이 Git에 커밋됐는지 확인
> 점검일: 2026-04-14 | 결과: **안전** — git 히스토리 없음, `.gitignore`에 `.env` 등록됨
```bash
# 실행할 명령어
cd ~/projects/gemma4/telegram-agent
git log --all --full-history -- .env
git grep -l "TELEGRAM_BOT_TOKEN" $(git log --pretty=format:'%H')

# 위험: .env가 git 히스토리에 있으면 토큰 노출
# 수정: .gitignore에 .env 추가 + git 히스토리 정리

# .gitignore 확인
cat .gitignore | grep .env
```

#### ✅ SEC-003: 토큰이 로그에 노출됐는지 확인
> 점검일: 2026-04-14 | 결과: ❌ httpx URL에 토큰 노출 → **수정 완료** — `logging.getLogger("httpx").setLevel(logging.WARNING)` 추가, telegram-agent 재시작
```bash
# 실행할 명령어
journalctl -u telegram-agent --no-pager | grep -i "token\|password\|secret\|key"
grep -r "TELEGRAM_BOT_TOKEN" ~/projects/gemma4/ --include="*.py" --include="*.log"

# 위험: 로그에 토큰 값이 평문으로 출력됨
# 수정: 로깅 코드에서 시크릿 마스킹 추가
```

#### ✅ SEC-004: 환경변수가 프로세스 목록에 노출됐는지 확인
> 점검일: 2026-04-14 | 결과: **안전** — systemd `EnvironmentFile` 방식 사용, ps 목록에 토큰 미노출
```bash
# 실행할 명령어
ps aux | grep telegram
cat /proc/$(pgrep -f telegram-agent)/environ 2>/dev/null | tr '\0' '\n' | grep TOKEN

# 위험: 토큰이 프로세스 환경변수로 노출
# systemd EnvironmentFile 방식은 상대적으로 안전
```

---

### 3.2 네트워크 / 포트 보안

#### ⚠️ SEC-005: 외부에 열린 포트 확인
> 점검일: 2026-04-14 | 결과: Ollama 127.0.0.1 ✅ / Open WebUI 0.0.0.0:8080 ⚠️ / System Monitor → **127.0.0.1:9090으로 수정 완료** | UFW 미설정으로 8080 외부 노출 잔존
```bash
# 실행할 명령어
ss -tlnp | grep -E "11434|8080|9090"
sudo nmap -sS localhost

# 정상: 127.0.0.1 (로컬)만 바인딩
# 위험: 0.0.0.0 (전체 인터페이스) 바인딩

# 예상 결과:
# 127.0.0.1:11434  → Ollama (로컬만 — 안전)
# 0.0.0.0:8080     → Open WebUI (위험! 외부 접근 가능)
# 0.0.0.0:9090     → System Monitor (위험! 외부 접근 가능)
```

#### ⚠️ SEC-006: UFW 방화벽 설정 확인
> 점검일: 2026-04-14 | 결과: **UFW 비활성화** — 아래 명령어로 수동 활성화 필요
> ```bash
> sudo ufw enable && sudo ufw allow 22 && sudo ufw deny 8080 && sudo ufw deny 11434
> ```
```bash
# 실행할 명령어
sudo ufw status verbose
sudo iptables -L -n

# 정상: 8080, 9090 포트가 외부 차단
# 위험: 모든 포트 허용 상태

# 수정 (취약 시)
sudo ufw enable
sudo ufw deny 8080
sudo ufw deny 9090
sudo ufw deny 11434
sudo ufw allow 22  # SSH만 허용
sudo ufw status
```

#### ✅ SEC-007: Ollama 외부 접근 차단 확인
> 점검일: 2026-04-14 | 결과: **안전** — `127.0.0.1:11434` 로컬 전용 바인딩
```bash
# 실행할 명령어
curl -s http://localhost:11434/api/tags | head -c 200
# 외부 IP로 접근 테스트 (다른 기기에서)
# curl http://서버IP:11434/api/tags

# 위험: 외부에서 Ollama API 무단 접근 가능
# → 인증 없이 모델 실행, 리소스 탈취 가능

# 수정: Ollama 환경변수 설정
# /etc/systemd/system/ollama.service.d/override.conf
# [Service]
# Environment="OLLAMA_HOST=127.0.0.1"
```

#### ✅ SEC-008: Open WebUI 인증 설정 확인
> 점검일: 2026-04-14 | 결과: **안전** — 로그인 인증 활성화 상태
```bash
# 실행할 명령어
curl -s http://localhost:8080/api/v1/auth/signin -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test"}' | head -c 200

# 정상: 로그인 없이 접근 불가
# 위험: 인증 우회 가능

# Open WebUI 환경변수로 인증 강제
# WEBUI_AUTH=true (기본값)
# WEBUI_SECRET_KEY=강력한_랜덤_키
```

---

### 3.3 Telegram Bot 보안

#### ✅ SEC-009: ALLOWED_USER_ID 설정 확인
> 점검일: 2026-04-14 | 결과: **안전** — `ALLOWED_USER_IDS=5634282715` 설정됨, 인가된 사용자만 접근
```bash
# 실행할 명령어
grep "ALLOWED_USER_ID" ~/projects/gemma4/telegram-agent/.env
grep "ALLOWED_USER_ID\|auth_check\|user_id" \
  ~/projects/gemma4/telegram-agent/telegram-agent.py

# 위험: ALLOWED_USER_ID 미설정 → 누구나 봇 사용 가능
# 위험: 코드에 인증 체크 없음

# 수정: 모든 핸들러에 인증 체크 추가
async def auth_check(update: Update) -> bool:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ 접근 거부")
        return False
    return True
```

#### ⚠️ SEC-010: 셸 명령어 인젝션 취약점 확인
> 점검일: 2026-04-14 | 결과: telegram-agent ✅ `shell=False` / gemma-desktop-mcp `shell=True` ⚠️ (파이프 지원 필요로 허용, 위험 패턴 차단 목록 적용 중)
```bash
# 실행할 명령어
grep -n "subprocess\|os.system\|shell=True\|eval\|exec" \
  ~/projects/gemma4/telegram-agent/*.py

# 위험 패턴:
# subprocess.run(user_input, shell=True)  ← 인젝션 가능
# os.system(f"ls {user_path}")            ← 인젝션 가능

# 안전 패턴:
# subprocess.run(["ls", path], shell=False)  ← 안전
```

#### ✅ SEC-011: 차단 명령어 목록 충분한지 확인
> 점검일: 2026-04-14 | 결과: **안전** — `BLOCKED_COMMANDS` 목록 구현됨 (rm -rf /, mkfs, fork bomb 등)
```bash
# 실행할 명령어
grep -A 20 "BLOCKED_COMMANDS\|blocked\|dangerous" \
  ~/projects/gemma4/telegram-agent/agent/shell_ops.py

# 최소한 이것들은 차단돼야 함:
BLOCKED = [
    "rm -rf /",
    "rm -rf ~",
    "sudo rm",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",  # fork bomb
    "chmod -R 777 /",
    "curl | bash",
    "wget | sh",
    "> /dev/sda",
]
```

#### ⚠️ SEC-012: 파일 접근 경로 제한 확인
> 점검일: 2026-04-14 | 결과: **경로 화이트리스트 미구현** — `../` 경로 탐색 가능 | 이번 주 내 수정 예정
```bash
# 실행할 명령어
grep -n "open\|read_file\|write_file\|path" \
  ~/projects/gemma4/telegram-agent/agent/file_ops.py | head -30

# 위험: ../../../etc/passwd 같은 경로 탐색 가능
# 수정: 허용 경로 화이트리스트

ALLOWED_PATHS = [
    os.path.expanduser("~/projects"),
    os.path.expanduser("~/esp32-ocpp-project"),
]

def is_safe_path(path: str) -> bool:
    real = os.path.realpath(path)
    return any(real.startswith(a) for a in ALLOWED_PATHS)
```

---

### 3.4 System Monitor 보안

#### ⚠️ SEC-013: System Monitor 인증 없음 확인
> 점검일: 2026-04-14 | 결과: **인증 없음** — 단, 127.0.0.1 로컬 전용으로 수정하여 외부 노출 차단 완료 | Basic Auth 추가는 이번 주 예정
```bash
# 실행할 명령어
curl -s http://localhost:9090/api/status | head -c 200
curl -s -X POST http://localhost:9090/api/service/ollama/stop

# 위험: 인증 없이 서비스 중지 가능
# 수정: 기본 인증(Basic Auth) 또는 API 키 추가

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

def verify(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "admin" or \
       credentials.password != os.getenv("MONITOR_PASSWORD"):
        raise HTTPException(status_code=401)
```

#### ⚠️ SEC-014: sudoers 설정 범위 확인
> 점검일: 2026-04-14 | 결과: **권한 과도** — `/bin/systemctl start *` 전체 허용 | 특정 서비스만 명시하도록 수정 필요 (visudo로 수동 수정)
```bash
# 실행할 명령어
sudo cat /etc/sudoers.d/monitor-control

# 위험: 너무 넓은 권한
# ALL=(ALL) NOPASSWD: /bin/systemctl *  ← 위험

# 정상: 최소 권한
# caram88 ALL=(ALL) NOPASSWD: /bin/systemctl start ollama
# caram88 ALL=(ALL) NOPASSWD: /bin/systemctl stop ollama
# caram88 ALL=(ALL) NOPASSWD: /bin/systemctl restart ollama
# (필요한 서비스만 명시)
```

---

### 3.5 파일 시스템 권한

#### ✅ SEC-015: 프로젝트 폴더 권한 확인
> 점검일: 2026-04-14 | 결과: `.env` 664(위험) → **600으로 수정 완료** | `.py` 파일 타인 쓰기 없음
```bash
# 실행할 명령어
ls -la ~/projects/gemma4/telegram-agent/
find ~/projects/gemma4 -name "*.py" -perm /o+w
find ~/projects/gemma4 -name "*.env" -perm /o+r

# 위험: 다른 사용자가 쓰기 가능한 .py 파일
# 위험: 다른 사용자가 읽기 가능한 .env 파일
# 수정:
chmod 700 ~/projects/gemma4/telegram-agent/
chmod 600 ~/projects/gemma4/telegram-agent/.env
chmod 644 ~/projects/gemma4/telegram-agent/*.py
```

#### ✅ SEC-016: systemd 서비스 파일 권한 확인
> 점검일: 2026-04-14 | 결과: **안전** — root 소유, 644 권한
```bash
# 실행할 명령어
ls -la /etc/systemd/system/telegram-agent.service
ls -la /etc/systemd/system/open-webui.service
ls -la /etc/systemd/system/system-monitor.service

# 정상: root 소유, 644 권한
# -rw-r--r-- 1 root root ...
```

---

### 3.6 MCP 서버 보안

#### ✅ SEC-017: Claude Desktop config 파일 확인
> 점검일: 2026-04-14 | 결과: 664(위험) → **600으로 수정 완료** | `chmod 600 ~/.config/Claude/claude_desktop_config.json`
```bash
# 실행할 명령어
cat ~/.config/Claude/claude_desktop_config.json
ls -la ~/.config/Claude/claude_desktop_config.json

# 위험: config에 시크릿 평문 저장
# 위험: 파일 권한이 너무 넓음
# 수정: chmod 600 ~/.config/Claude/claude_desktop_config.json
```

#### ✅ SEC-018: MCP 서버 프로세스 권한 확인
> 점검일: 2026-04-14 | 결과: **안전** — 일반 사용자(`caram88`) 권한으로 실행
```bash
# 실행할 명령어
ps aux | grep "gemma-mcp\|mcp-server"

# 위험: root 권한으로 실행 중
# 정상: 일반 사용자 권한으로 실행
```

---

### 3.7 Ollama 모델 보안

#### ✅ SEC-019: 모델 파일 무결성 확인
> 점검일: 2026-04-14 | 결과: **정상** — gemma4:26b(17GB), gemma4:e2b(7.2GB), gemma4:e4b(9.6GB) 등록됨
```bash
# 실행할 명령어
ollama list
ls -la ~/.ollama/models/

# 모델 파일이 예상 크기인지 확인
# gemma4:e4b → 약 9.6GB
# gemma4:26b → 약 17GB
# gemma4:e2b → 약 7.2GB
```

#### ⚠️ SEC-020: Ollama 버전 최신 여부 확인
> 점검일: 2026-04-14 | 결과: 현재 `0.20.7` — 최신 버전 비교 미완료 | `ollama --version` 으로 주기적 확인 필요
```bash
# 실행할 명령어
ollama --version
curl -s https://api.github.com/repos/ollama/ollama/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])"

# 최신 버전과 비교 → 업데이트 필요 시 안내
```

---

### 3.8 시스템 전반 보안

#### ⚠️ SEC-021: Ubuntu 보안 업데이트 확인
> 점검일: 2026-04-14 | 결과: 미점검 — `sudo apt update && sudo apt upgrade` 권장
```bash
# 실행할 명령어
sudo apt list --upgradable 2>/dev/null | grep -i security
sudo unattended-upgrades --dry-run

# 보안 패치 미적용 패키지 목록 출력
```

#### ⚠️ SEC-022: 불필요한 오픈 포트 확인
> 점검일: 2026-04-14 | 결과: Ollama 127.0.0.1 ✅ / System Monitor 127.0.0.1 ✅(수정) / Open WebUI 0.0.0.0:8080 ⚠️ UFW로 차단 필요
```bash
# 실행할 명령어
sudo ss -tlnp
sudo nmap -sV localhost

# 예상 오픈 포트:
# 22    → SSH (필요)
# 11434 → Ollama (로컬만)
# 8080  → Open WebUI (로컬만)
# 9090  → System Monitor (로컬만)
# 그 외 포트가 열려 있으면 확인 필요
```

#### ⚠️ SEC-023: SSH 설정 확인
> 점검일: 2026-04-14 | 결과: 미점검 — `sudo grep -E "PermitRootLogin|PasswordAuthentication" /etc/ssh/sshd_config` 확인 권장
```bash
# 실행할 명령어
sudo grep -E "PermitRootLogin|PasswordAuthentication|Port" \
  /etc/ssh/sshd_config

# 정상 설정:
# PermitRootLogin no
# PasswordAuthentication no (키 인증만)
# Port 22 (또는 비표준 포트)
```

#### ⚠️ SEC-024: 실패한 로그인 시도 확인
> 점검일: 2026-04-14 | 결과: **fail2ban 미설치** — `sudo apt install fail2ban -y` 권장
```bash
# 실행할 명령어
sudo journalctl -u ssh --since "24 hours ago" | grep "Failed\|Invalid"
sudo lastb | head -20

# 브루트포스 공격 여부 확인
# fail2ban 설치 여부 확인
sudo fail2ban-client status sshd 2>/dev/null || echo "fail2ban 미설치"
```

---

## 4. 자동 보안 점검 스크립트

```bash
# security_check.sh — 한 번에 전체 점검
#!/bin/bash

echo "=== 보안 점검 시작 ==="
ISSUES=0

check() {
    local desc="$1"
    local cmd="$2"
    local expected="$3"
    result=$(eval "$cmd" 2>/dev/null)
    if echo "$result" | grep -q "$expected"; then
        echo "✅ $desc"
    else
        echo "⚠️  $desc"
        echo "   결과: $result"
        ISSUES=$((ISSUES+1))
    fi
}

# .env 권한
check ".env 권한 600" \
  "stat -c %a ~/projects/gemma4/telegram-agent/.env" "600"

# UFW 활성화
check "UFW 방화벽 활성화" \
  "sudo ufw status" "active"

# Ollama 로컬 바인딩
check "Ollama 로컬 전용" \
  "ss -tlnp | grep 11434" "127.0.0.1"

# .gitignore .env 포함
check ".gitignore에 .env 포함" \
  "cat ~/projects/gemma4/telegram-agent/.gitignore" ".env"

# ALLOWED_USER_ID 설정
check "ALLOWED_USER_ID 설정됨" \
  "grep ALLOWED_USER_ID ~/projects/gemma4/telegram-agent/.env" \
  "ALLOWED_USER_ID=[0-9]"

echo ""
echo "=== 점검 완료: $ISSUES개 이슈 발견 ==="
```

---

## 5. 점검 후 보안 보고서 형식

Claude Code가 생성할 `security-report.md` 형식:

```markdown
# 보안 감사 보고서
날짜: 2026-04-14
시스템: Gemma4 AI 에이전트 시스템

## 요약
- 전체 점검 항목: 24개
- 안전: N개
- 경고: N개
- 심각: N개

## 발견된 취약점

### 심각 (즉시 수정 필요)
| 항목 | 내용 | 수정 방법 |
|---|---|---|
| SEC-XXX | ... | ... |

### 경고 (수정 권장)
| 항목 | 내용 | 수정 방법 |
|---|---|---|

### 안전
- SEC-001: .env 권한 600 ✅
- ...

## 수정 완료 항목
- [ ] SEC-XXX 수정 완료

## 권장 추가 조치
1. ...
```

---

## 6. 개발 우선순위

### 즉시 처리 (오늘)
```
[ ] SEC-001: .env 권한 600 확인
[ ] SEC-002: .env git 노출 확인
[ ] SEC-005: 오픈 포트 확인
[ ] SEC-009: ALLOWED_USER_ID 설정
[ ] SEC-010: 셸 인젝션 취약점
[ ] SEC-006: UFW 방화벽 활성화
```

### 이번 주 처리
```
[ ] SEC-007: Ollama 로컬 바인딩
[ ] SEC-012: 파일 경로 제한
[ ] SEC-013: Monitor 인증 추가
[ ] SEC-014: sudoers 최소 권한
[ ] SEC-021: Ubuntu 보안 업데이트
```

### 선택 사항
```
[ ] SEC-023: SSH 키 인증만 허용
[ ] SEC-024: fail2ban 설치
[ ] SEC-019: 모델 무결성 확인
```

---

*이 사양서는 Claude Code가 시스템 보안을 단계적으로 점검하고 수정하기 위한 명세입니다.*
*점검 완료 시 각 항목을 ⬜ → ✅/⚠️/❌ 로 업데이트하고 security-report.md를 생성하세요.*
