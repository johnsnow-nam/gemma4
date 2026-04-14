# Claude Desktop + Gemma4 통합 사양서
> Claude Desktop의 핵심 기능을 Gemma4(Ollama)로 확장하는 MCP 기반 통합 시스템  
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

## 1. 프로젝트 개요

### 1.1 목표
```
Claude Desktop (claude.ai 앱)
        +
Gemma4 MCP 서버 (로컬 Ollama)
        =
Claude Desktop에서 로컬 Gemma4를 도구로 활용
→ Claude API 비용 절감 + 로컬 파일 접근 + 프라이버시 보호
```

### 1.2 핵심 아이디어
- Claude Desktop은 MCP(Model Context Protocol) 서버를 연결할 수 있음
- Gemma4를 MCP 서버로 감싸면 Claude Desktop에서 Gemma4를 도구처럼 사용 가능
- 복잡한 추론 → Claude API / 단순 반복 작업 → 로컬 Gemma4 자동 라우팅

### 1.3 기술 스택
```
Claude Desktop  ← MCP 프로토콜 ← Gemma4 MCP 서버 ← Ollama
     ↑                                  ↑
  GUI 인터페이스                    Python FastMCP
  파일 드래그앤드롭                  로컬 파일 접근
  Desktop Extension                이미지 분석
```

### 1.4 시스템 구성도
```
사용자
  ↓ Claude Desktop GUI
Claude Desktop (claude.ai 앱)
  ↓ MCP 프로토콜 (stdio / HTTP)
gemma-mcp-server.py
  ├── ollama_tool          → Gemma4 추론
  ├── file_tool            → 로컬 파일 읽기/쓰기
  ├── folder_tool          → 폴더 탐색
  ├── image_tool           → 이미지 분석
  ├── shell_tool           → 셸 명령어 실행
  ├── git_tool             → Git 연동
  └── project_tool         → 프로젝트 컨텍스트 관리
```

### 1.5 프로젝트 구조
```
gemma-desktop-mcp/
├── gemma-mcp-server.py      # MCP 서버 메인
├── tools/
│   ├── __init__.py
│   ├── ollama_tool.py       # Gemma4 추론 도구
│   ├── file_tool.py         # 파일 읽기/쓰기
│   ├── folder_tool.py       # 폴더 탐색
│   ├── image_tool.py        # 이미지 분석
│   ├── shell_tool.py        # 셸 실행
│   ├── git_tool.py          # Git 연동
│   └── project_tool.py      # 프로젝트 관리
├── config/
│   └── settings.py          # 설정
├── install.sh               # 자동 설치 스크립트
└── README.md
```

---

## 2. Claude Desktop 기본 기능 (이미 제공)

> 아래는 Claude Desktop이 기본으로 제공하는 기능 — 별도 개발 불필요

| 기능 | 상태 | 비고 |
|---|---|---|
| 대화 UI (채팅) | ✅ 기본 제공 | claude.ai 앱 |
| 파일 드래그앤드롭 | ✅ 기본 제공 | PDF, 이미지, 문서 |
| 프로젝트 (컨텍스트 저장) | ✅ 기본 제공 | Pro 플랜 |
| 아티팩트 (코드/문서 생성) | ✅ 기본 제공 | |
| 대화 히스토리 | ✅ 기본 제공 | |
| MCP 서버 연결 | ✅ 기본 제공 | config.json |
| Desktop Extension | ✅ 기본 제공 | .mcpb 파일 |
| Cowork (파일 작업) | ✅ 기본 제공 | Mac M1+ 전용 |
| 웹 검색 | ✅ 기본 제공 | |
| 이미지 생성 | ✅ 기본 제공 | |

---

## 3. 개발 대상: Gemma4 MCP 서버

### 3.1 MCP 서버 설정 파일

#### ✅ SETUP-001: claude_desktop_config.json 설정
```
위치 (Linux): ~/.config/Claude/claude_desktop_config.json
내용:
{
  "mcpServers": {
    "gemma4-local": {
      "command": "python3",
      "args": ["/home/caram88/gemma-desktop-mcp/gemma-mcp-server.py"],
      "env": {
        "OLLAMA_URL": "http://localhost:11434",
        "DEFAULT_MODEL": "gemma4:26b"
      }
    }
  }
}
```

#### ✅ SETUP-002: 자동 설치 스크립트
```bash
# install.sh 실행 시:
1. pip install fastmcp ollama 설치
2. claude_desktop_config.json 자동 생성/업데이트
3. Claude Desktop 재시작 안내
4. 연결 테스트 실행
```

---

### 3.2 도구 (Tools) 구현

#### ✅ T-001: ask_gemma (핵심 추론 도구)
```
도구명:   ask_gemma
설명:     로컬 Gemma4 모델에게 질문
파라미터:
  - prompt (str): 질문 내용
  - model (str): 사용 모델 (기본: gemma4:26b)
  - temperature (float): 창의성 (기본: 0.3)
  - stream (bool): 스트리밍 여부

Claude Desktop에서 사용 예시:
"ask_gemma 도구로 이 코드를 분석해줘"
→ Claude가 ask_gemma 도구 호출
→ Gemma4가 로컬에서 분석
→ 결과를 Claude Desktop에 표시

구현:
from fastmcp import FastMCP
import ollama

mcp = FastMCP("gemma4-local")

@mcp.tool()
def ask_gemma(prompt: str, model: str = "gemma4:26b") -> str:
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.message.content
```

#### ✅ T-002: read_file (파일 읽기)
```
도구명:   read_file
설명:     로컬 파일 내용 읽기
파라미터:
  - path (str): 파일 경로
  - encoding (str): 인코딩 (기본: utf-8)

Claude Desktop에서 사용 예시:
"~/esp32-project/main.c 파일을 read_file로 읽어서 분석해줘"
→ Claude가 read_file 호출
→ 파일 내용 반환
→ Claude가 내용 분석 후 답변
```

#### ✅ T-003: read_folder (폴더 탐색)
```
도구명:   read_folder
설명:     폴더 내 파일 목록 및 내용 수집
파라미터:
  - path (str): 폴더 경로
  - pattern (str): 파일 패턴 (기본: **/*.c,**/*.h,**/*.py)
  - max_files (int): 최대 파일 수 (기본: 30)
  - include_content (bool): 내용 포함 여부

Claude Desktop에서 사용 예시:
"~/esp32-ocpp-project 폴더를 read_folder로 읽어서
 OCPP 구현 현황을 파악해줘"
```

#### ✅ T-004: write_file (파일 쓰기)
```
도구명:   write_file
설명:     파일 생성 또는 수정
파라미터:
  - path (str): 저장 경로
  - content (str): 파일 내용
  - backup (bool): 백업 생성 여부 (기본: true)
  - mode (str): "write" | "append"

보안:
  - 허용된 디렉터리만 쓰기 가능 (홈 폴더 내)
  - /etc, /usr, /sys 등 시스템 경로 차단
  - 쓰기 전 사용자 확인 프롬프트 (Claude Desktop에서)
```

#### ✅ T-005: analyze_image (이미지 분석)
```
도구명:   analyze_image
설명:     이미지 파일을 Gemma4 vision으로 분석
파라미터:
  - path (str): 이미지 경로
  - prompt (str): 분석 질문
  - model (str): vision 모델 (기본: gemma4:26b)

지원 형식: .png .jpg .jpeg .webp
Claude Desktop에서 사용 예시:
"~/Desktop/schematic.png 를 analyze_image로 분석해서
 SPI 연결 방식을 확인해줘"
```

#### ✅ T-006: run_shell (셸 명령어 실행)
```
도구명:   run_shell
설명:     셸 명령어 실행 후 결과 반환
파라미터:
  - command (str): 실행할 명령어
  - cwd (str): 작업 디렉터리
  - timeout (int): 타임아웃 초 (기본: 30)

보안:
  - rm -rf 등 위험 명령어 차단 리스트
  - sudo 명령어 차단
  - 실행 전 사용자 확인

Claude Desktop에서 사용 예시:
"run_shell로 ninja -C build 실행하고 에러 분석해줘"
```

#### ✅ T-007: git_status (Git 상태)
```
도구명:   git_status
설명:     Git 저장소 상태 확인
파라미터:
  - path (str): 저장소 경로

반환값:
  - 브랜치명
  - 변경된 파일 목록
  - Staged 파일 목록
  - 최근 커밋 3개

Claude Desktop에서 사용 예시:
"git_status로 현재 변경사항 확인하고
 커밋 메시지 작성해줘"
```

#### ✅ T-008: git_diff (Git Diff 분석)
```
도구명:   git_diff
설명:     변경된 코드 diff 가져오기
파라미터:
  - path (str): 저장소 경로
  - staged (bool): staged diff 여부

Claude Desktop에서 사용 예시:
"git_diff 결과를 바탕으로 코드 리뷰해줘"
```

#### ✅ T-009: search_files (파일 내용 검색)
```
도구명:   search_files
설명:     폴더 내 파일에서 텍스트 검색 (grep)
파라미터:
  - path (str): 검색 경로
  - query (str): 검색어
  - pattern (str): 파일 패턴
  - regex (bool): 정규식 여부

Claude Desktop에서 사용 예시:
"esp32 프로젝트에서 ocpp_send_boot_notification
 함수 사용처를 search_files로 찾아줘"
```

#### ✅ T-010: get_system_info (시스템 정보)
```
도구명:   get_system_info
설명:     GPU, VRAM, 모델 상태 등 시스템 정보
반환값:
  - GPU 모델 및 VRAM 사용량
  - 로드된 Ollama 모델 목록
  - 디스크 여유 공간
  - CPU/RAM 사용률

Claude Desktop에서 사용 예시:
"현재 시스템 상태를 get_system_info로 확인해줘"
```

#### ✅ T-011: list_ollama_models (모델 목록)
```
도구명:   list_ollama_models
설명:     설치된 Ollama 모델 목록 조회
반환값:
  - 모델명, 크기, 수정일, 퀀타이제이션

Claude Desktop에서 사용 예시:
"사용 가능한 로컬 모델 목록 보여줘"
```

#### ✅ T-012: ask_gemma_with_files (파일 포함 분석)
```
도구명:   ask_gemma_with_files
설명:     파일 내용과 함께 Gemma4에게 질문 (복합 도구)
파라미터:
  - file_paths (list): 파일 경로 목록
  - prompt (str): 질문
  - model (str): 모델

Claude Desktop에서 사용 예시:
"main.c, ocpp.c, uart.h 세 파일을
 ask_gemma_with_files로 분석해서
 메모리 누수 찾아줘"
```

---

### 3.3 리소스 (Resources) 구현

#### ✅ R-001: 프로젝트 프로파일 리소스
```
리소스 URI: gemma://profiles/{name}
설명:       프로젝트별 시스템 프롬프트 저장
내용:
  - esp32: ESP32 IDF 전문가 프롬프트
  - ocpp: OCPP 1.6 전문가 프롬프트
  - general: 범용 코딩 어시스턴트

Claude Desktop에서 사용:
"gemma://profiles/esp32 프로파일로 분석해줘"
```

#### ✅ R-002: 최근 파일 리소스
```
리소스 URI: gemma://recent-files
설명:       최근 접근한 파일 목록 제공
```

---

### 3.4 프롬프트 (Prompts) 구현

#### ✅ PR-001: 코드 리뷰 프롬프트
```
프롬프트명: code_review
파라미터:   file_path
동작:       파일 읽기 + Gemma4 코드 리뷰 자동 실행
```

#### ✅ PR-002: 버그 분석 프롬프트
```
프롬프트명: debug_analysis
파라미터:   error_log, file_path
동작:       에러 로그 + 코드 분석 자동 실행
```

#### ✅ PR-003: 커밋 메시지 생성 프롬프트
```
프롬프트명: generate_commit
파라미터:   repo_path
동작:       git diff 읽기 + Conventional Commits 메시지 생성
```

---

## 4. Claude Desktop 연동 시나리오

### 시나리오 1: 로컬 파일 분석
```
[사용자 → Claude Desktop]
"~/esp32-project/main.c 파일의 OCPP 연결 로직을 분석해줘"

[Claude Desktop → MCP 서버]
1. read_file("~/esp32-project/main.c") 호출
2. 파일 내용 반환

[Claude]
3. 파일 내용 기반으로 분석 답변
   (또는 ask_gemma_with_files로 Gemma4에게 위임)
```

### 시나리오 2: 이미지 + 코드 동시 분석
```
[사용자 → Claude Desktop]
파일 드래그앤드롭: schematic.png
"이 회로도와 @spi_driver.c 코드가 일치하는지 확인해줘"

[Claude Desktop → MCP 서버]
1. analyze_image("schematic.png", "SPI 연결 핀 확인")
2. read_file("spi_driver.c")

[Claude]
3. 이미지 분석 결과 + 코드 비교 → 답변
```

### 시나리오 3: 빌드 에러 자동 분석
```
[사용자 → Claude Desktop]
"빌드 실행하고 에러 분석해줘"

[Claude Desktop → MCP 서버]
1. run_shell("ninja -C build") 실행
2. stderr 출력 캡처
3. ask_gemma(에러 내용 + 프롬프트) 호출

[Claude]
4. Gemma4 분석 결과 기반으로 해결책 제시
```

### 시나리오 4: 자동 커밋 메시지
```
[사용자 → Claude Desktop]
"변경사항 확인하고 커밋 메시지 만들어줘"

[Claude Desktop → MCP 서버]
1. git_status("~/esp32-project") 호출
2. git_diff("~/esp32-project") 호출
3. ask_gemma("Conventional Commits 형식으로 메시지 생성")

[Claude]
4. 생성된 메시지 확인 → run_shell("git commit -m '...'")
```

### 시나리오 5: 프로젝트 전체 분석
```
[사용자 → Claude Desktop]
"ESP32 프로젝트 전체 구조 파악하고
 OCPP 구현 진행 상황 보고해줘"

[Claude Desktop → MCP 서버]
1. read_folder("~/esp32-project") 호출
2. ask_gemma_with_files(파일 목록, "OCPP 구현 현황 분석")

[Claude]
3. Gemma4 분석 결과 기반으로 상세 보고서 작성
```

---

## 5. 스마트 라우팅 전략

```
Claude Desktop 수신 요청
        ↓
복잡도 / 비용 분류
        ↓
┌────────────────────────────────┐
│ 단순 반복 / 로컬 작업          │ → ask_gemma (Gemma4, 무료)
│ - 파일 요약                    │
│ - 코드 포맷팅                  │
│ - 간단한 설명                  │
└────────────────────────────────┘
        ↓
┌────────────────────────────────┐
│ 복잡한 추론 / 설계             │ → Claude API (유료, 고품질)
│ - 아키텍처 설계                │
│ - 복잡한 버그 원인 분석        │
│ - 중요한 코드 리뷰             │
└────────────────────────────────┘
```

---

## 6. 설치 방법

### 자동 설치 (install.sh)
```bash
# 1. 저장소 클론
git clone https://github.com/username/gemma-desktop-mcp
cd gemma-desktop-mcp

# 2. 설치 실행
chmod +x install.sh
./install.sh

# 3. Claude Desktop 재시작
# 4. Claude Desktop 하단 MCP 아이콘 확인
```

### 수동 설치
```bash
# 의존성 설치
pip install fastmcp ollama

# claude_desktop_config.json 편집
nano ~/.config/Claude/claude_desktop_config.json

# 내용 추가:
{
  "mcpServers": {
    "gemma4-local": {
      "command": "python3",
      "args": ["/home/caram88/gemma-desktop-mcp/gemma-mcp-server.py"]
    }
  }
}

# Claude Desktop 재시작
```

---

## 7. 도구 목록 전체 요약

| 도구명 | 기능 | 상태 |
|---|---|---|
| `ask_gemma` | Gemma4 추론 | ✅ |
| `ask_gemma_with_files` | 파일 포함 추론 | ✅ |
| `read_file` | 파일 읽기 | ✅ |
| `write_file` | 파일 쓰기 | ✅ |
| `read_folder` | 폴더 탐색 | ✅ |
| `search_files` | 파일 내용 검색 | ✅ |
| `analyze_image` | 이미지 분석 | ✅ |
| `run_shell` | 셸 명령어 실행 | ✅ |
| `git_status` | Git 상태 | ✅ |
| `git_diff` | Git Diff | ✅ |
| `get_system_info` | 시스템 정보 | ✅ |
| `list_ollama_models` | 모델 목록 | ✅ |

---

## 8. 개발 우선순위 (Phase)

### Phase 1 — MVP (1일)
```
[ ] SETUP-001: claude_desktop_config.json 설정
[ ] T-001: ask_gemma 기본 추론
[ ] T-002: read_file 파일 읽기
[ ] T-003: read_folder 폴더 탐색
[ ] MCP 서버 기동 및 Claude Desktop 연결 확인
```

### Phase 2 — 핵심 기능 (2~3일)
```
[ ] T-004: write_file 파일 쓰기
[ ] T-005: analyze_image 이미지 분석
[ ] T-006: run_shell 셸 실행
[ ] T-007: git_status Git 상태
[ ] T-012: ask_gemma_with_files 복합 도구
[ ] SETUP-002: install.sh 자동 설치
```

### Phase 3 — 고급 기능 (1주)
```
[ ] T-008: git_diff
[ ] T-009: search_files
[ ] T-010: get_system_info
[ ] T-011: list_ollama_models
[ ] R-001: 프로파일 리소스
[ ] PR-001~003: 자동화 프롬프트
[ ] 스마트 라우팅 로직
```

---

## 9. Claude Code 실행 명령

```bash
cd ~/gemma-desktop-mcp
claude

# Claude Code에게 입력:
"gemma-desktop-mcp-spec.md 파일을 읽고
 Phase 1 MVP부터 구현해줘.
 fastmcp 라이브러리 사용.
 구현 완료된 항목은 ⬜ → ✅ 로 spec 파일도 업데이트해줘.
 완성되면 Claude Desktop에서 테스트할 수 있게
 install.sh도 만들어줘."
```

---

## 10. 테스트 시나리오

```
# Claude Desktop 실행 후 하단 MCP 아이콘 클릭
# "gemma4-local" 서버 도구 목록 확인

# 테스트 1: 기본 추론
"ask_gemma 도구로 OCPP BootNotification 필드를 설명해줘"

# 테스트 2: 파일 읽기
"read_file로 ~/esp32-project/main.c 읽어서 분석해줘"

# 테스트 3: 이미지 분석
(회로도 이미지 드래그앤드롭)
"analyze_image로 이 회로도의 SPI 핀 찾아줘"

# 테스트 4: 빌드 실행
"run_shell로 ninja -C ~/esp32-project/build 실행해줘"

# 테스트 5: 전체 통합
"read_folder로 ~/esp32-project 읽고
 ask_gemma_with_files로 OCPP 구현 현황 분석해줘"
```

---

## 11. gemma-cli vs Claude Desktop MCP 비교

| 항목 | gemma-cli (터미널) | Claude Desktop MCP |
|---|---|---|
| 인터페이스 | 터미널 CLI | GUI 앱 |
| AI 모델 | Gemma4만 | Claude + Gemma4 |
| 파일 접근 | @ 문법 | MCP 도구 |
| 이미지 분석 | @ 문법 | 드래그앤드롭 + 도구 |
| 대화 UI | 텍스트 | 그래픽 |
| 개발 필요 | Python CLI | Python MCP 서버 |
| 사용 난이도 | 개발자용 | 일반 사용자도 가능 |
| 비용 | 완전 무료 | Claude API + 무료 Gemma4 |

**두 가지를 함께 쓰는 것이 최적:**
- 빠른 코드 작업 → gemma-cli (터미널)
- 파일 분석 + 이미지 + 고품질 추론 → Claude Desktop + Gemma4 MCP

---

*이 사양서는 Claude Code가 gemma-desktop-mcp를 단계적으로 구현하기 위한 명세입니다.*  
*구현 완료 시 각 항목을 ⬜ → ✅ 로 업데이트하세요.*
