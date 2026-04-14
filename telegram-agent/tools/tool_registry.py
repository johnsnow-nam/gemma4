"""TOOL-001: 툴 레지스트리 (명령어 라우팅 테이블)"""
from __future__ import annotations

# 명령어 → (설명, 사용법) 매핑
COMMAND_REGISTRY: dict[str, tuple[str, str]] = {
    "/start":    ("봇 시작 / 웰컴 메시지", "/start"),
    "/help":     ("전체 명령어 목록", "/help"),
    "/status":   ("시스템 + 에이전트 상태", "/status"),
    "/projects": ("등록된 프로젝트 목록", "/projects"),
    "/project":  ("프로젝트 전환",         "/project <이름>"),
    "/model":    ("현재 모델 확인 / 변경",  "/model [모델명]"),
    "/clear":    ("대화 메모리 초기화",      "/clear"),
    "/save":     ("현재 대화 세션 저장",     "/save [파일명]"),
    "/build":    ("현재 프로젝트 빌드",      "/build"),
    "/diff":     ("git diff 확인",          "/diff"),
    "/commit":   ("변경사항 자동 커밋",      "/commit"),
    "/tree":     ("프로젝트 폴더 트리",      "/tree"),
}


def get_help_text() -> str:
    lines = ["*📋 사용 가능한 명령어*\n"]
    for cmd, (desc, usage) in COMMAND_REGISTRY.items():
        lines.append(f"`{cmd}` — {desc}")
        if usage != cmd:
            lines.append(f"   사용법: `{usage}`")
    lines.append("\n*💬 일반 메시지*")
    lines.append("명령어 없이 텍스트를 보내면 AI가 답변합니다.")
    lines.append("`!<명령어>` 형식으로 셸 명령어를 직접 실행할 수 있습니다.")
    lines.append("\n*📷 이미지*")
    lines.append("사진을 보내면 AI가 이미지를 분석합니다.")
    return "\n".join(lines)
