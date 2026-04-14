#!/usr/bin/env python3
"""
gemma-mcp-server — Claude Desktop + Gemma4(Ollama) MCP 통합 서버

실행: python3 gemma-mcp-server.py
Claude Desktop config.json에 등록 후 자동 실행됩니다.
"""
from __future__ import annotations

import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from config.settings import DEFAULT_MODEL, OLLAMA_URL

# ──────────────────────────────────────────────
# MCP 서버 초기화
# ──────────────────────────────────────────────
mcp = FastMCP(
    name="gemma4-local",
    instructions=(
        "Gemma4 로컬 AI + 파일 시스템 접근 도구 모음입니다.\n"
        "로컬 파일 읽기/쓰기, Gemma4 추론, 이미지 분석, 셸 실행, Git 연동을 제공합니다.\n"
        f"기본 모델: {DEFAULT_MODEL}  Ollama: {OLLAMA_URL}"
    ),
)


# ══════════════════════════════════════════════
# T-001: ask_gemma — 핵심 추론 도구
# ══════════════════════════════════════════════
@mcp.tool()
def ask_gemma(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    system: str = "",
) -> str:
    """
    로컬 Gemma4 모델에게 질문합니다.

    - prompt: 질문 내용
    - model: 사용할 모델 (기본: gemma4:26b, 빠른 버전: gemma4:e4b)
    - temperature: 창의성 (0.0~1.0, 기본 0.3)
    - system: 시스템 프롬프트 (선택)
    """
    from tools.ollama_tool import ask_gemma as _ask
    return _ask(prompt=prompt, model=model, temperature=temperature, system=system)


# ══════════════════════════════════════════════
# T-012: ask_gemma_with_files — 파일 포함 복합 도구
# ══════════════════════════════════════════════
@mcp.tool()
def ask_gemma_with_files(
    file_paths: list[str],
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
) -> str:
    """
    파일 내용과 함께 Gemma4에게 질문합니다. (이미지 포함 가능)

    - file_paths: 파일 경로 목록 (텍스트 파일 + 이미지 혼합 가능)
    - prompt: 분석 질문
    - model: 사용할 모델
    - temperature: 창의성
    """
    from tools.ollama_tool import ask_gemma_with_files as _ask
    return _ask(file_paths=file_paths, prompt=prompt, model=model, temperature=temperature)


# ══════════════════════════════════════════════
# T-002: read_file — 파일 읽기
# ══════════════════════════════════════════════
@mcp.tool()
def read_file(path: str, encoding: str = "auto") -> str:
    """
    로컬 파일을 읽어 내용을 반환합니다.

    - path: 파일 경로 (예: ~/esp32-project/main.c)
    - encoding: 인코딩 (auto/utf-8/euc-kr)
    """
    from tools.file_tool import read_file as _read
    return _read(path=path, encoding=encoding)


# ══════════════════════════════════════════════
# T-004: write_file — 파일 쓰기
# ══════════════════════════════════════════════
@mcp.tool()
def write_file(
    path: str,
    content: str,
    backup: bool = True,
    mode: str = "write",
) -> str:
    """
    파일을 생성하거나 수정합니다. 홈 폴더 이하만 허용됩니다.

    - path: 저장 경로
    - content: 파일 내용
    - backup: 기존 파일 백업 여부 (기본: true, .bak 생성)
    - mode: "write" (덮어쓰기) 또는 "append" (추가)
    """
    from tools.file_tool import write_file as _write
    return _write(path=path, content=content, backup=backup, mode=mode)


# ══════════════════════════════════════════════
# T-003: read_folder — 폴더 탐색
# ══════════════════════════════════════════════
@mcp.tool()
def read_folder(
    path: str,
    pattern: str = "**/*.c,**/*.h,**/*.py,**/*.js,**/*.ts,**/*.md,**/*.json",
    max_files: int = 30,
    include_content: bool = True,
) -> str:
    """
    폴더 내 파일 목록 및 내용을 수집합니다.

    - path: 폴더 경로 (예: ~/esp32-project)
    - pattern: 파일 패턴 (쉼표로 구분, 예: **/*.c,**/*.h)
    - max_files: 최대 파일 수 (기본: 30)
    - include_content: 파일 내용 포함 여부
    """
    from tools.folder_tool import read_folder as _read
    return _read(path=path, pattern=pattern, max_files=max_files, include_content=include_content)


# ══════════════════════════════════════════════
# T-005: analyze_image — 이미지 분석
# ══════════════════════════════════════════════
@mcp.tool()
def analyze_image(
    path: str,
    prompt: str = "이 이미지를 상세히 분석해줘.",
    model: str = DEFAULT_MODEL,
) -> str:
    """
    이미지 파일을 Gemma4 vision으로 분석합니다.

    - path: 이미지 파일 경로 (.png .jpg .jpeg .webp .bmp)
    - prompt: 분석 질문 (예: "SPI 핀 번호를 찾아줘")
    - model: vision 모델 (기본: gemma4:26b)
    """
    from tools.image_tool import analyze_image as _analyze
    return _analyze(path=path, prompt=prompt, model=model)


# ══════════════════════════════════════════════
# T-006: run_shell — 셸 명령어 실행
# ══════════════════════════════════════════════
@mcp.tool()
def run_shell(
    command: str,
    cwd: str = "~",
    timeout: int = 30,
) -> str:
    """
    셸 명령어를 실행하고 결과를 반환합니다.
    sudo, rm -rf 등 위험 명령어는 자동으로 차단됩니다.

    - command: 실행할 명령어 (예: ninja -C build)
    - cwd: 작업 디렉터리 (기본: 홈 폴더)
    - timeout: 타임아웃 초 (기본: 30)
    """
    from tools.shell_tool import run_shell as _run
    return _run(command=command, cwd=cwd, timeout=timeout)


# ══════════════════════════════════════════════
# T-007: git_status — Git 상태
# ══════════════════════════════════════════════
@mcp.tool()
def git_status(path: str = ".") -> str:
    """
    Git 저장소 상태를 확인합니다.
    브랜치명, 변경 파일 목록, staged 파일, 최근 커밋을 반환합니다.

    - path: 저장소 경로 (기본: 현재 디렉터리)
    """
    from tools.git_tool import git_status as _status
    return _status(path=path)


# ══════════════════════════════════════════════
# T-008: git_diff — Git Diff
# ══════════════════════════════════════════════
@mcp.tool()
def git_diff(path: str = ".", staged: bool = False) -> str:
    """
    Git 변경 내용(diff)을 가져옵니다.

    - path: 저장소 경로
    - staged: True이면 staged(add된) 변경사항만
    """
    from tools.git_tool import git_diff as _diff
    return _diff(path=path, staged=staged)


# ══════════════════════════════════════════════
# T-009: search_files — 파일 내용 검색
# ══════════════════════════════════════════════
@mcp.tool()
def search_files(
    path: str,
    query: str,
    pattern: str = "*",
    use_regex: bool = False,
    max_results: int = 100,
) -> str:
    """
    폴더 내 파일에서 텍스트를 검색합니다. (grep 대체)

    - path: 검색 경로
    - query: 검색어 (문자열 또는 정규식)
    - pattern: 파일 패턴 (예: *.c, *.py)
    - use_regex: 정규식 사용 여부
    - max_results: 최대 결과 수
    """
    from tools.project_tool import search_files as _search
    return _search(path=path, query=query, pattern=pattern, use_regex=use_regex, max_results=max_results)


# ══════════════════════════════════════════════
# T-010: get_system_info — 시스템 정보
# ══════════════════════════════════════════════
@mcp.tool()
def get_system_info() -> str:
    """
    GPU, VRAM, CPU, RAM, 디스크, Ollama 모델 상태 등 시스템 정보를 반환합니다.
    """
    from tools.project_tool import get_system_info as _info
    return _info()


# ══════════════════════════════════════════════
# T-011: list_ollama_models — 모델 목록
# ══════════════════════════════════════════════
@mcp.tool()
def list_ollama_models() -> str:
    """
    설치된 Ollama 모델 목록을 조회합니다.
    모델명, 크기, 퀀타이제이션, 수정일을 포함합니다.
    """
    from tools.project_tool import list_ollama_models as _list
    return _list()


# ══════════════════════════════════════════════
# R-001: 프로파일 리소스 (gemma://profiles/{name})
# ══════════════════════════════════════════════
BUILTIN_PROFILES = {
    "esp32": {
        "name": "ESP32 전문가",
        "system": (
            "당신은 ESP32 임베디드 개발 전문가입니다. "
            "FreeRTOS, ESP-IDF, Arduino 프레임워크에 능통합니다. "
            "C/C++ 코드를 중심으로 도움을 드리며, 하드웨어 제약사항을 항상 고려합니다. "
            "한국어로 답변합니다."
        ),
    },
    "ocpp": {
        "name": "OCPP 전문가",
        "system": (
            "당신은 OCPP (Open Charge Point Protocol) 1.6J / 2.0.1 전문가입니다. "
            "충전소 관리 시스템(CSMS)과 충전기(CP) 간의 WebSocket 통신, "
            "상태 머신 구현, JSON 메시지 처리에 전문성이 있습니다. "
            "한국어로 답변합니다."
        ),
    },
    "general": {
        "name": "범용 개발 어시스턴트",
        "system": (
            "당신은 숙련된 소프트웨어 개발 어시스턴트입니다. "
            "코드 분석, 버그 수정, 리팩토링, 문서화를 도와드립니다. "
            "한국어로 답변하며 코드는 마크다운 코드블록으로 작성합니다."
        ),
    },
    "korean": {
        "name": "한국어 특화 어시스턴트",
        "system": (
            "당신은 한국어 특화 AI 어시스턴트입니다. "
            "모든 응답을 자연스러운 한국어로 작성합니다. "
            "기술 문서, 코드 설명, 번역 등 다양한 작업을 도와드립니다."
        ),
    },
}


@mcp.resource("gemma://profiles/{name}")
def get_profile(name: str) -> str:
    """R-001: 프로젝트 프로파일 — Gemma4용 시스템 프롬프트"""
    profile = BUILTIN_PROFILES.get(name)
    if not profile:
        available = ", ".join(BUILTIN_PROFILES.keys())
        return f"프로파일 '{name}'을 찾을 수 없습니다. 사용 가능: {available}"

    return (
        f"# 프로파일: {profile['name']}\n\n"
        f"**시스템 프롬프트:**\n{profile['system']}\n\n"
        f"---\n"
        f"이 프로파일을 사용하려면 ask_gemma 호출 시 "
        f'system="{profile["system"]}" 을 전달하세요.'
    )


@mcp.resource("gemma://profiles/")
def list_profiles() -> str:
    """R-001: 사용 가능한 프로파일 목록"""
    lines = ["# Gemma4 프로파일 목록\n"]
    for key, prof in BUILTIN_PROFILES.items():
        lines.append(f"- **{key}**: {prof['name']}")
        lines.append(f"  URI: `gemma://profiles/{key}`")
    return "\n".join(lines)


# ══════════════════════════════════════════════
# R-002: 최근 파일 리소스
# ══════════════════════════════════════════════
@mcp.resource("gemma://recent-files")
def get_recent_files() -> str:
    """R-002: 최근 접근한 파일 목록"""
    from tools.file_tool import get_recent_files as _recent
    files = _recent()
    if not files:
        return "최근 접근한 파일이 없습니다."
    lines = ["# 최근 파일 목록\n"]
    for f in files:
        lines.append(f"- `{f}`")
    return "\n".join(lines)


# ══════════════════════════════════════════════
# PR-001: code_review 프롬프트
# ══════════════════════════════════════════════
@mcp.prompt()
def code_review(file_path: str) -> str:
    """PR-001: 파일 읽기 + Gemma4 코드 리뷰 자동 실행"""
    from tools.file_tool import read_file as _read
    content = _read(file_path)
    return (
        f"다음 파일을 코드 리뷰해줘. "
        f"버그, 보안 취약점, 성능 문제, 개선사항을 구체적으로 지적해줘:\n\n"
        f"{content}"
    )


# ══════════════════════════════════════════════
# PR-002: debug_analysis 프롬프트
# ══════════════════════════════════════════════
@mcp.prompt()
def debug_analysis(error_log: str, file_path: str = "") -> str:
    """PR-002: 에러 로그 + 코드 분석 자동 실행"""
    parts = [
        "다음 에러 로그와 코드를 분석해서 원인과 해결책을 제시해줘:\n\n",
        f"## 에러 로그\n```\n{error_log}\n```",
    ]
    if file_path:
        from tools.file_tool import read_file as _read
        content = _read(file_path)
        parts.append(f"\n## 코드\n{content}")
    return "\n".join(parts)


# ══════════════════════════════════════════════
# PR-003: generate_commit 프롬프트
# ══════════════════════════════════════════════
@mcp.prompt()
def generate_commit(repo_path: str = ".") -> str:
    """PR-003: git diff 읽기 + Conventional Commits 메시지 생성"""
    from tools.git_tool import git_diff as _diff
    diff = _diff(path=repo_path, staged=True)
    if "[staged 변경사항 없음]" in diff:
        diff = _diff(path=repo_path, staged=False)
    return (
        "다음 git diff를 분석하여 Conventional Commits 형식의 커밋 메시지를 생성해줘.\n"
        "형식: type(scope): description\n"
        "type: feat, fix, docs, refactor, test, chore, style, perf\n"
        "규칙:\n"
        "- 제목은 50자 이내\n"
        "- 한국어로 작성\n"
        "- 커밋 메시지 한 줄만 출력\n\n"
        f"{diff}"
    )


# ══════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
