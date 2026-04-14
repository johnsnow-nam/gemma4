# Telegram AI 에이전트 개발 사양서
> 텔레그램에서 메시지를 보내면 Ubuntu 서버에서 AI가 대신 작업 수행  
> 작성일: 2026-04-14  
> 개발 대상: Claude Code에게 전달하는 구현 명세서

---

## 개발 현황 범례

| 기호 | 의미 |
|---|---|
| ✅ | 개발 완료 |
| 🔧 | 개발 중 |
| ⬜ | 미개발 |
| ❌ | 제외 (스코프 아웃) |

---

## 1. 개요

### 1.1 목표
```
[Yonghee 스마트폰 텔레그램]
  "esp32 프로젝트 빌드하고 에러 고쳐줘"
        ↓ Telegram Bot API
[Ubuntu 서버 (RTX 5070)]
  AI 에이전트 실행
  → 파일 읽기
  → 코드 수정
  → 빌드 실행
  → 결과 보고
        ↓ Telegram Bot API
[Yonghee 스마트폰 텔레그램]
  "✅ 빌드 성공. 수정 내역: uart.c 87번줄 free() 추가"
```

### 1.2 방법 2가지

#### 방법 A: Claude Code Channels (공식, 15분 설치)
```
장점: 공식 지원, 보안 강함, 설정 간단
단점: Claude API 비용 발생, feature flag 롤아웃 중
명령: claude --channels plugin:telegram@claude-plugins-official
```

#### 방법 B: 자체 구현 Telegram 에이전트 (완전 무료)
```
장점: 완전 무료, Gemma4 로컬, 완전 커스텀
단점: 직접 개발 필요 (이 사양서 목적)
구성: Python + Telegram Bot API + Ollama(Gemma4) + 파일/셸 도구
```

> 이 사양서는 **방법 B (자체 구현)** 기준

### 1.3 기술 스택
```
언어:        Python 3.11+
텔레그램:    python-telegram-bot 21.x
AI 백엔드:   Ollama (gemma4:26b) — 무료 로컬
파일 작업:   pathlib, glob, subprocess
Git 연동:    gitpython
의존성:      pip install python-telegram-bot ollama gitpython rich
실행:        python3 telegram-agent.py
```

### 1.4 프로젝트 구조
```
telegram-agent/
├── telegram-agent.py        # 메인 봇 진입점
├── agent/
│   ├── __init__.py
│   ├── brain.py             # AI 추론 (Gemma4)
│   ├── executor.py          # 작업 실행 엔진
│   ├── file_ops.py          # 파일 읽기/쓰기
│   ├── shell_ops.py         # 셸 명령어 실행
│   ├── git_ops.py           # Git 작업
│   └── memory.py            # 대화 메모리
├── config/
│   ├── settings.py          # 설정
│   └── projects.yaml        # 프로젝트 목록
├── tools/
│   └── tool_registry.py     # 도구 등록/관리
├── .env                     # 텔레그램 토큰 (gitignore)
├── install.sh               # 자동 설치
└── README.md
```

---

## 2. 설정 및 설치

### ⬜ SETUP-001: Telegram Bot 생성
```
1. 텔레그램에서 @BotFather 검색
2. /newbot 입력
3. 봇 이름 입력 (예: YongheeAgent)
4. 봇 ID 입력 (예: yonghee_agent_bot)
5. 발급된 TOKEN 복사
6. .env 파일에 저장:
   TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
   ALLOWED_USER_ID=본인_텔레그램_ID
```

### ⬜ SETUP-002: 본인 텔레그램 ID 확인
```
1. 텔레그램에서 @userinfobot 검색
2. /start 입력
3. 출력된 숫자 ID를 ALLOWED_USER_ID에 저장
→ 본인만 봇 사용 가능하도록 보안 설정
```

### ✅ SETUP-003: 자동 설치 스크립트 (install.sh)
```bash
#!/bin/bash
# 1. 의존성 설치
pip install python-telegram-bot ollama gitpython rich python-dotenv

# 2. .env 파일 생성
echo "TELEGRAM_BOT_TOKEN=" >> .env
echo "ALLOWED_USER_ID=" >> .env
chmod 600 .env

# 3. systemd 서비스 등록 (부팅 시 자동 시작)
sudo tee /etc/systemd/system/telegram-agent.service > /dev/null << EOF
[Unit]
Description=Telegram AI Agent
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
EnvironmentFile=$(pwd)/.env
ExecStart=/usr/bin/python3 $(pwd)/telegram-agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable telegram-agent
sudo systemctl start telegram-agent
echo "✅ 설치 완료. 텔레그램 봇에서 /start 입력"
```

### ✅ SETUP-004: 프로젝트 설정 (projects.yaml)
```yaml
projects:
  esp32-ocpp:
    path: ~/esp32-ocpp-project
    description: ESP32 OCPP 1.6 충전기 펌웨어
    build_command: ninja -C build
    language: c
    system_prompt: |
      당신은 ESP32 IDF + OCPP 1.6 전문가입니다.
      이 프로젝트는 EV 충전기 펌웨어입니다.

  mi0802:
    path: ~/mi0802-firmware
    description: MI0802 열화상 카메라 펌웨어
    build_command: idf.py build
    language: c
    system_prompt: |
      당신은 ESP32-S3 + MI0802 센서 전문가입니다.

default_project: esp32-ocpp
default_model: gemma4:26b
```

---

## 3. 핵심 기능 구현

### 3.1 메인 봇 (telegram-agent.py)

#### ✅ CORE-001: 봇 기본 구조
```python
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from agent.brain import AgentBrain
from agent.executor import TaskExecutor
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER_ID"))

brain = AgentBrain()
executor = TaskExecutor()

async def auth_check(update: Update) -> bool:
    """본인만 사용 가능"""
    if update.effective_user.id != ALLOWED_USER:
        await update.message.reply_text("⛔ 접근 거부")
        return False
    return True

async def handle_message(update: Update, context):
    if not await auth_check(update):
        return

    user_msg = update.message.text
    # 타이핑 표시
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # AI 에이전트 실행
    result = await executor.run(user_msg)
    await update.message.reply_text(result, parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("projects", projects_cmd))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    print("✅ 텔레그램 에이전트 시작")
    app.run_polling()
```

### 3.2 AI 추론 엔진 (brain.py)

#### ✅ BRAIN-001: Gemma4 추론
```python
import ollama
from agent.memory import ConversationMemory

class AgentBrain:
    def __init__(self, model="gemma4:26b"):
        self.model = model
        self.memory = ConversationMemory()

    async def think(self, user_input: str,
                    context: str = "",
                    system_prompt: str = "") -> str:
        """Gemma4로 추론"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 이전 대화 포함
        messages.extend(self.memory.get_recent(10))

        # 컨텍스트(파일 내용 등) 포함
        if context:
            user_input = f"{context}\n\n{user_input}"

        messages.append({"role": "user", "content": user_input})

        response = ollama.chat(model=self.model, messages=messages)
        reply = response.message.content

        # 메모리 저장
        self.memory.add("user", user_input)
        self.memory.add("assistant", reply)

        return reply

    async def think_with_image(self, prompt: str, image_path: str) -> str:
        """이미지 포함 추론"""
        import base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        response = ollama.chat(
            model=self.model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [img_b64]
            }]
        )
        return response.message.content
```

### 3.3 작업 실행 엔진 (executor.py)

#### ✅ EXEC-001: 자연어 → 작업 파싱 및 실행
```python
import re
from agent.brain import AgentBrain
from agent.file_ops import FileOps
from agent.shell_ops import ShellOps
from agent.git_ops import GitOps
import yaml

class TaskExecutor:
    def __init__(self):
        self.brain = AgentBrain()
        self.file_ops = FileOps()
        self.shell_ops = ShellOps()
        self.git_ops = GitOps()
        self.current_project = self._load_default_project()

    async def run(self, user_input: str) -> str:
        """
        자연어 명령을 분석하여 적절한 작업 실행
        """
        lower = user_input.lower()

        # 1. 빌드 관련
        if any(k in lower for k in ["빌드", "build", "컴파일", "compile"]):
            return await self._handle_build(user_input)

        # 2. 파일 분석
        elif any(k in lower for k in ["분석", "읽어", "확인", "analyze", "read"]):
            return await self._handle_file_analysis(user_input)

        # 3. 코드 수정
        elif any(k in lower for k in ["수정", "고쳐", "fix", "수정해", "변경"]):
            return await self._handle_code_fix(user_input)

        # 4. Git 작업
        elif any(k in lower for k in ["커밋", "commit", "git", "상태"]):
            return await self._handle_git(user_input)

        # 5. 셸 실행
        elif user_input.startswith("!"):
            return await self._handle_shell(user_input[1:])

        # 6. 프로젝트 전환
        elif any(k in lower for k in ["프로젝트", "project", "전환"]):
            return await self._handle_project_switch(user_input)

        # 7. 일반 질문 → AI 답변
        else:
            return await self.brain.think(
                user_input,
                system_prompt=self.current_project.get("system_prompt", "")
            )

    async def _handle_build(self, user_input: str) -> str:
        """빌드 실행 및 에러 자동 분석"""
        project = self.current_project
        build_cmd = project.get("build_command", "make")
        project_path = os.path.expanduser(project["path"])

        # 빌드 실행
        result = await self.shell_ops.run(
            build_cmd, cwd=project_path, timeout=120
        )

        if result["returncode"] == 0:
            return f"✅ *빌드 성공*\n```\n{result['stdout'][-500:]}\n```"
        else:
            # 에러 → AI 분석
            error_text = result["stderr"][-2000:]
            analysis = await self.brain.think(
                f"다음 빌드 에러를 분석하고 수정 방법을 알려줘:\n```\n{error_text}\n```",
                system_prompt=project.get("system_prompt", "")
            )
            return f"❌ *빌드 실패*\n\n{analysis}"

    async def _handle_file_analysis(self, user_input: str) -> str:
        """파일/폴더 내용 읽어서 AI 분석"""
        project_path = os.path.expanduser(
            self.current_project["path"]
        )

        # 파일명 추출 시도
        file_match = re.search(r'(\w+\.[ch])', user_input)
        if file_match:
            filename = file_match.group(1)
            content = self.file_ops.find_and_read(project_path, filename)
        else:
            # 파일명 없으면 프로젝트 전체 요약
            content = self.file_ops.read_project_summary(project_path)

        return await self.brain.think(
            user_input,
            context=content,
            system_prompt=self.current_project.get("system_prompt", "")
        )

    async def _handle_code_fix(self, user_input: str) -> str:
        """코드 수정 요청 처리"""
        project_path = os.path.expanduser(
            self.current_project["path"]
        )

        # 관련 파일 찾기
        file_match = re.search(r'(\w+\.[ch])', user_input)
        if not file_match:
            return "⚠️ 수정할 파일명을 알려주세요. 예: 'uart.c 에서 메모리 누수 고쳐줘'"

        filename = file_match.group(1)
        content = self.file_ops.find_and_read(project_path, filename)

        if not content:
            return f"⚠️ {filename} 파일을 찾을 수 없습니다."

        # AI에게 수정 요청
        fix_prompt = f"""
다음 파일을 수정해줘. 수정된 전체 코드를 ```c ... ``` 블록으로 감싸서 제공해줘.

요청: {user_input}

현재 코드:
{content}
"""
        response = await self.brain.think(
            fix_prompt,
            system_prompt=self.current_project.get("system_prompt", "")
        )

        # 코드 블록 추출 및 파일 저장
        code_match = re.search(r'```(?:c|cpp)?\n(.*?)```', response, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1)
            saved_path = self.file_ops.save_with_backup(
                project_path, filename, fixed_code
            )
            return (
                f"✅ *{filename} 수정 완료*\n"
                f"백업: {saved_path}.bak\n\n"
                f"*변경 내역:*\n{response[:500]}"
            )
        else:
            return response

    async def _handle_git(self, user_input: str) -> str:
        """Git 작업"""
        project_path = os.path.expanduser(self.current_project["path"])
        status = self.git_ops.get_status(project_path)

        if "커밋" in user_input or "commit" in user_input.lower():
            diff = self.git_ops.get_diff(project_path)
            msg = await self.brain.think(
                f"다음 변경사항에 대한 Conventional Commits 형식의 커밋 메시지를 만들어줘:\n{diff}",
                system_prompt="짧고 명확한 영어 커밋 메시지 1줄만 출력해줘."
            )
            result = self.git_ops.commit(project_path, msg.strip())
            return f"✅ 커밋 완료\n`{msg.strip()}`"
        else:
            return f"📊 *Git 상태*\n```\n{status}\n```"
```

### 3.4 파일 작업 (file_ops.py)

#### ✅ FILE-001: 파일 읽기/쓰기/검색
```python
import os, glob, shutil
from pathlib import Path

class FileOps:
    IGNORE_DIRS = {'.git', 'build', 'node_modules', '.cache', '__pycache__'}
    SOURCE_EXTS = {'.c', '.h', '.cpp', '.py', '.js', '.ts', '.md', '.yaml'}

    def find_and_read(self, project_path: str, filename: str) -> str:
        """파일명으로 프로젝트 내 검색 후 읽기"""
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            if filename in files:
                filepath = os.path.join(root, filename)
                return self._read_file(filepath)
        return ""

    def read_project_summary(self, project_path: str,
                              max_files: int = 15) -> str:
        """프로젝트 핵심 파일 요약"""
        files = []
        for root, dirs, filenames in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for f in filenames:
                if Path(f).suffix in self.SOURCE_EXTS:
                    files.append(os.path.join(root, f))
                if len(files) >= max_files:
                    break

        result = []
        for fp in files:
            content = self._read_file(fp, max_lines=50)
            rel_path = os.path.relpath(fp, project_path)
            result.append(f"[{rel_path}]\n{content}")

        return "\n\n".join(result)

    def save_with_backup(self, project_path: str,
                          filename: str, content: str) -> str:
        """파일 저장 (자동 백업)"""
        filepath = self.find_file_path(project_path, filename)
        if not filepath:
            filepath = os.path.join(project_path, filename)

        # 백업
        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath

    def _read_file(self, path: str, max_lines: int = 500) -> str:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            if len(lines) > max_lines:
                return ''.join(lines[:max_lines]) + f"\n... ({len(lines)}줄 중 {max_lines}줄)"
            return ''.join(lines)
        except Exception as e:
            return f"[읽기 실패: {e}]"
```

### 3.5 셸 실행 (shell_ops.py)

#### ✅ SHELL-001: 안전한 셸 실행
```python
import asyncio, subprocess

BLOCKED_COMMANDS = ['rm -rf /', 'sudo rm', 'mkfs', ':(){:|:&};:']

class ShellOps:
    async def run(self, command: str, cwd: str = None,
                  timeout: int = 60) -> dict:
        # 위험 명령어 차단
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return {"returncode": -1, "stdout": "",
                        "stderr": f"⛔ 차단된 명령어: {blocked}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"returncode": -1, "stdout": "",
                    "stderr": f"⏱ 타임아웃 ({timeout}초)"}
```

### 3.6 Git 작업 (git_ops.py)

#### ✅ GIT-001: Git 연동
```python
import subprocess

class GitOps:
    def get_status(self, repo_path: str) -> str:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path, capture_output=True, text=True
        )
        return result.stdout or "변경사항 없음"

    def get_diff(self, repo_path: str) -> str:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_path, capture_output=True, text=True
        )
        return result.stdout[:3000]  # 3000자 제한

    def commit(self, repo_path: str, message: str) -> bool:
        subprocess.run(["git", "add", "-A"], cwd=repo_path)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, capture_output=True, text=True
        )
        return result.returncode == 0
```

### 3.7 대화 메모리 (memory.py)

#### ✅ MEM-001: 세션 메모리 관리
```python
import json
from datetime import datetime
from pathlib import Path

class ConversationMemory:
    def __init__(self, max_turns: int = 20):
        self.messages = []
        self.max_turns = max_turns
        self.save_dir = Path("~/.telegram-agent/sessions").expanduser()
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        # 최대 턴 수 유지
        if len(self.messages) > self.max_turns * 2:
            self.messages = self.messages[-self.max_turns * 2:]

    def get_recent(self, n: int) -> list:
        return self.messages[-n * 2:]

    def clear(self):
        self.messages = []

    def save(self, name: str = None):
        name = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.save_dir / f"{name}.json"
        with open(path, 'w') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)
        return str(path)
```

---

## 4. 텔레그램 커맨드 목록

| 커맨드 | 기능 | 상태 |
|---|---|---|
| `/start` | 봇 시작 및 안내 | ✅ |
| `/status` | 시스템 상태 (GPU, 모델) | ✅ |
| `/projects` | 프로젝트 목록 | ✅ |
| `/project [이름]` | 프로젝트 전환 | ✅ |
| `/model [이름]` | AI 모델 전환 | ✅ |
| `/clear` | 대화 메모리 초기화 | ✅ |
| `/save` | 현재 세션 저장 | ✅ |
| `/help` | 전체 도움말 | ✅ |

---

## 5. 자연어 작업 패턴

| 텔레그램 메시지 | 동작 | 상태 |
|---|---|---|
| `빌드해줘` | 현재 프로젝트 빌드 실행 | ✅ |
| `에러 분석해줘` | 최근 빌드 에러 AI 분석 | ✅ |
| `main.c 분석해줘` | 파일 읽고 AI 분석 | ✅ |
| `uart.c 메모리 누수 고쳐줘` | 코드 자동 수정 | ✅ |
| `git 상태 알려줘` | git status 출력 | ✅ |
| `커밋해줘` | 자동 커밋 메시지 생성 후 커밋 | ✅ |
| `프로젝트 구조 보여줘` | 폴더 트리 출력 | ✅ |
| `!ls -la src/` | 셸 명령어 직접 실행 | ✅ |
| (이미지 전송) | 이미지 AI 분석 (회로도, 파형 등) | ✅ |
| `mi0802 프로젝트로 바꿔` | 프로젝트 전환 | ✅ |

---

## 6. 개발 우선순위 (Phase)

### Phase 1 — MVP (1일)
```
[ ] SETUP-001~003: Telegram Bot 생성 + 설치
[ ] CORE-001: 기본 봇 구조
[ ] BRAIN-001: Gemma4 추론
[ ] EXEC-001: 자연어 파싱 기본
[ ] FILE-001: 파일 읽기
[ ] SHELL-001: 셸 실행
목표: 텔레그램에서 메시지 보내면 Gemma4가 답변
```

### Phase 2 — 핵심 기능 (2~3일)
```
[ ] 빌드 실행 + 에러 자동 분석
[ ] 파일 수정 + 자동 저장
[ ] Git 상태/커밋
[ ] 이미지 분석 (회로도, 파형)
[ ] 프로젝트 전환
[ ] 대화 메모리
```

### Phase 3 — 고급 기능 (1주)
```
[ ] MEM-001: 장기 메모리 (파일 저장)
[ ] 주기적 작업 (Cron — "매시간 빌드 체크")
[ ] 알림 발송 (빌드 실패 시 자동 텔레그램 알림)
[ ] 멀티 프로젝트 동시 관리
[ ] 작업 큐 (긴 작업 백그라운드 실행)
```

---

## 7. Claude Code 실행 명령

```bash
cd ~/telegram-agent
claude

# Claude Code에게 입력:
"telegram-agent-spec.md 파일을 읽고
 Phase 1 MVP부터 구현 시작해줘.

 핵심 우선순위:
 1. python-telegram-bot으로 기본 봇 동작
 2. Ollama gemma4:26b 연동
 3. 파일 읽기(@파일명 또는 자연어)
 4. 셸 명령어 실행(!명령어)
 5. 빌드 실행 + 에러 AI 분석

 환경:
 - Ubuntu 22.04
 - Python 3.11
 - Ollama 실행 중 (localhost:11434)
 - 프로젝트: ~/esp32-ocpp-project

 구현 완료된 항목은 ⬜ → ✅ 로
 spec 파일도 업데이트해줘.
 완성되면 install.sh도 만들어줘."
```

---

## 8. 방법 A: Claude Code Channels (공식 15분 설정)

> 자체 구현 없이 바로 쓰고 싶다면:

```bash
# 1. Claude Code 최신 버전 확인
claude --version  # v2.1.80 이상 필요

# 2. Telegram 플러그인 설치
claude plugin marketplace add claude-plugins-official/telegram

# 3. 텔레그램 봇 토큰 설정
mkdir -p ~/.claude/channels/telegram
echo "TELEGRAM_BOT_TOKEN=YOUR_TOKEN" > ~/.claude/channels/telegram/.env
chmod 600 ~/.claude/channels/telegram/.env

# 4. Channels 모드로 실행
claude --channels plugin:telegram@claude-plugins-official

# 5. 텔레그램에서 /telegram:configure 입력
```

**주의:** Claude Code Channels는 현재 feature flag 롤아웃 중 — 계정에 따라 미지원일 수 있음

---

## 9. 테스트 시나리오

```
# 스마트폰 텔레그램에서 테스트

[Yonghee] /start
[봇] 안녕하세요! ESP32 에이전트 준비됐습니다.
     현재 프로젝트: esp32-ocpp-project

[Yonghee] 빌드해줘
[봇] ⏳ 빌드 중...
[봇] ❌ 빌드 실패
     uart.c:87: error: use of undeclared identifier 'buf'
     
     분석: buf 변수가 선언되지 않았습니다.
     82번줄에 char buf[256]; 추가가 필요합니다.

[Yonghee] uart.c 고쳐줘
[봇] ✅ uart.c 수정 완료
     백업: uart.c.bak
     변경: 82번줄에 char buf[256]; 추가

[Yonghee] 다시 빌드해줘
[봇] ✅ 빌드 성공!
     Binary: build/firmware.bin (1.2MB)

[Yonghee] 커밋해줘
[봇] ✅ 커밋 완료
     "fix(uart): add missing buf declaration in uart_read()"

[Yonghee] (회로도 이미지 전송)
[봇] 이미지 분석 중...
     SPI 연결: MOSI=GPIO23, MISO=GPIO19, SCLK=GPIO18, CS=GPIO5
     QCA7000S 연결이 정상으로 보입니다.
```

---

*이 사양서는 Claude Code가 Telegram AI 에이전트를 단계적으로 구현하기 위한 명세입니다.*  
*구현 완료 시 각 항목을 ⬜ → ✅ 로 업데이트하세요.*
