"""EXEC-001: 자연어 명령 파싱 및 작업 실행 엔진"""
from __future__ import annotations
import logging
import os
import re

import yaml

from agent.brain import AgentBrain
from agent.file_ops import FileOps
from agent.shell_ops import ShellOps
from agent.git_ops import GitOps
from config.settings import PROJECTS_YAML, MAX_REPLY_LENGTH

logger = logging.getLogger(__name__)


def _load_projects() -> dict:
    if not os.path.exists(PROJECTS_YAML):
        return {}
    with open(PROJECTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _truncate(text: str, max_len: int = MAX_REPLY_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n_...({len(text) - max_len}자 생략)_"


class TaskExecutor:
    def __init__(self):
        self.brain = AgentBrain()
        self.file_ops = FileOps()
        self.shell_ops = ShellOps()
        self.git_ops = GitOps()

        cfg = _load_projects()
        self.projects: dict = cfg.get("projects", {})
        default_name = cfg.get("default_project", "")
        self.current_project_name = default_name
        self.current_project: dict = self.projects.get(default_name, {})
        self._last_build_error: str = ""

    # ──────────────────────────────────────────────
    # 메인 디스패처
    # ──────────────────────────────────────────────
    async def run(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        # !셸 명령어 직접 실행
        if text.startswith("!"):
            return await self._handle_shell(text[1:].strip())

        # 빌드 관련
        if any(k in lower for k in ["빌드", "build", "컴파일", "compile", "make", "ninja"]):
            return await self._handle_build(text)

        # 에러 분석 (빌드 에러 재분석)
        if any(k in lower for k in ["에러", "오류", "error", "에러 분석", "왜 안"]):
            return await self._handle_error_analysis(text)

        # 파일 수정
        if any(k in lower for k in ["수정", "고쳐", "fix", "변경", "바꿔", "패치"]):
            return await self._handle_code_fix(text)

        # 파일 분석/읽기
        if any(k in lower for k in ["분석", "읽어", "확인", "보여", "설명", "read", "analyze"]):
            return await self._handle_file_analysis(text)

        # 프로젝트 구조
        if any(k in lower for k in ["구조", "트리", "tree", "목록", "list"]):
            return await self._handle_structure(text)

        # 검색
        if any(k in lower for k in ["검색", "찾아", "search", "grep"]):
            return await self._handle_search(text)

        # Git 작업
        if any(k in lower for k in ["커밋", "commit", "git", "상태", "diff", "push"]):
            return await self._handle_git(text)

        # 프로젝트 전환
        if any(k in lower for k in ["프로젝트", "project", "전환", "바꿔"]):
            for name in self.projects:
                if name in lower:
                    return self._switch_project(name)

        # 일반 AI 질문
        return _truncate(
            self.brain.think(
                text,
                system_prompt=self.current_project.get("system_prompt", ""),
            )
        )

    # ──────────────────────────────────────────────
    # 빌드
    # ──────────────────────────────────────────────
    async def _handle_build(self, user_input: str) -> str:
        if not self.current_project:
            return "⚠️ 현재 프로젝트가 설정되지 않았습니다. `/projects` 로 확인하세요."

        project_path = self.current_project.get("path", "")
        build_cmd = self.current_project.get("build_command", "make")
        abs_path = os.path.expanduser(project_path)

        if not os.path.isdir(abs_path):
            return f"⚠️ 프로젝트 경로를 찾을 수 없습니다: `{project_path}`"

        result = await self.shell_ops.run(build_cmd, cwd=abs_path, timeout=180)

        if result["returncode"] == 0:
            stdout = result["stdout"][-1500:].strip()
            return f"✅ *빌드 성공*\n```\n{stdout}\n```"
        else:
            stderr = result["stderr"][-2000:].strip()
            stdout = result["stdout"][-500:].strip()
            self._last_build_error = stderr or stdout

            analysis = self.brain.think(
                f"다음 빌드 에러를 분석하고 원인과 해결 방법을 한국어로 설명해줘:\n```\n{self._last_build_error}\n```",
                system_prompt=self.current_project.get("system_prompt", ""),
                remember=False,
            )
            return _truncate(
                f"❌ *빌드 실패*\n\n```\n{self._last_build_error[:800]}\n```\n\n"
                f"*AI 분석:*\n{analysis}"
            )

    # ──────────────────────────────────────────────
    # 에러 분석
    # ──────────────────────────────────────────────
    async def _handle_error_analysis(self, user_input: str) -> str:
        error_ctx = self._last_build_error if self._last_build_error else ""
        analysis = self.brain.think(
            user_input,
            context=f"최근 빌드 에러:\n```\n{error_ctx}\n```" if error_ctx else "",
            system_prompt=self.current_project.get("system_prompt", ""),
        )
        return _truncate(analysis)

    # ──────────────────────────────────────────────
    # 파일 분석
    # ──────────────────────────────────────────────
    async def _handle_file_analysis(self, user_input: str) -> str:
        project_path = self.current_project.get("path", ".")

        # 파일명 추출 (*.c / *.h / *.py 등)
        file_match = re.search(r"(\w[\w./\-]*\.[a-zA-Z]{1,5})", user_input)
        if file_match:
            filename = file_match.group(1)
            content = self.file_ops.find_and_read(project_path, filename)
            if not content:
                return f"⚠️ `{filename}` 파일을 찾을 수 없습니다."
            context = content
        else:
            context = self.file_ops.read_project_summary(project_path)

        analysis = self.brain.think(
            user_input,
            context=context,
            system_prompt=self.current_project.get("system_prompt", ""),
        )
        return _truncate(analysis)

    # ──────────────────────────────────────────────
    # 코드 수정
    # ──────────────────────────────────────────────
    async def _handle_code_fix(self, user_input: str) -> str:
        project_path = self.current_project.get("path", ".")

        file_match = re.search(r"(\w[\w./\-]*\.[a-zA-Z]{1,5})", user_input)
        if not file_match:
            return "⚠️ 수정할 파일명을 알려주세요.\n예: `uart.c 메모리 누수 고쳐줘`"

        filename = file_match.group(1)
        content = self.file_ops.find_and_read(project_path, filename)
        if not content:
            return f"⚠️ `{filename}` 파일을 찾을 수 없습니다."

        lang = filename.rsplit(".", 1)[-1] if "." in filename else ""
        fix_prompt = (
            f"다음 파일을 수정해줘. 수정된 *전체 코드*를 ```{lang} ... ``` 블록으로 감싸서 제공해줘.\n\n"
            f"요청: {user_input}\n\n"
            f"현재 코드:\n{content}"
        )

        response = self.brain.think(
            fix_prompt,
            system_prompt=self.current_project.get("system_prompt", ""),
        )

        # 코드블록 추출
        code_match = re.search(r"```(?:\w+)?\n(.*?)```", response, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1)
            saved_path = self.file_ops.save_with_backup(project_path, filename, fixed_code)
            rel = os.path.relpath(saved_path, os.path.expanduser(project_path))
            return _truncate(
                f"✅ *{filename} 수정 완료*\n"
                f"경로: `{rel}`\n"
                f"백업: `{rel}.bak`\n\n"
                f"*변경 내역:*\n{response[:1000]}"
            )
        else:
            return _truncate(response)

    # ──────────────────────────────────────────────
    # 프로젝트 구조
    # ──────────────────────────────────────────────
    async def _handle_structure(self, user_input: str) -> str:
        project_path = self.current_project.get("path", ".")
        tree = self.file_ops.get_folder_tree(project_path)
        return f"📁 *{self.current_project_name} 구조*\n```\n{tree}\n```"

    # ──────────────────────────────────────────────
    # 파일 검색
    # ──────────────────────────────────────────────
    async def _handle_search(self, user_input: str) -> str:
        project_path = self.current_project.get("path", ".")
        # 검색어 추출 (따옴표 우선, 없으면 마지막 단어)
        quoted = re.search(r'["\'](.+?)["\']', user_input)
        if quoted:
            query = quoted.group(1)
        else:
            words = user_input.split()
            query = words[-1] if words else ""

        if not query:
            return "⚠️ 검색어를 알려주세요. 예: `ocpp_send 함수 찾아줘`"

        result = self.file_ops.search(project_path, query)
        return _truncate(f"🔍 *검색 결과*\n{result}")

    # ──────────────────────────────────────────────
    # Git
    # ──────────────────────────────────────────────
    async def _handle_git(self, user_input: str) -> str:
        project_path = self.current_project.get("path", ".")

        if not self.git_ops.is_repo(project_path):
            return f"⚠️ `{project_path}` 는 Git 저장소가 아닙니다."

        lower = user_input.lower()

        # 커밋
        if "커밋" in lower or "commit" in lower:
            diff = self.git_ops.get_diff(project_path)
            if "변경사항 없음" in diff:
                return "변경사항이 없어 커밋할 내용이 없습니다."
            msg = self.brain.think(
                f"다음 변경사항에 대해 Conventional Commits 형식의 영어 커밋 메시지 1줄만 출력해줘:\n```diff\n{diff}\n```",
                system_prompt="커밋 메시지 한 줄만 출력. 설명 없이.",
                remember=False,
            ).strip().strip('"').strip("'")
            ok, out = self.git_ops.commit(project_path, msg)
            if ok:
                return f"✅ *커밋 완료*\n`{msg}`"
            return f"❌ 커밋 실패\n```\n{out}\n```"

        # diff
        if "diff" in lower or "변경" in lower:
            diff = self.git_ops.get_diff(project_path)
            return _truncate(f"📝 *Git Diff*\n```diff\n{diff}\n```")

        # log
        if "로그" in lower or "log" in lower or "히스토리" in lower:
            log = self.git_ops.get_log(project_path)
            return f"📋 *최근 커밋*\n```\n{log}\n```"

        # 기본: 상태
        status = self.git_ops.get_status(project_path)
        return f"📊 *Git 상태 — {self.current_project_name}*\n```\n{status}\n```"

    # ──────────────────────────────────────────────
    # 셸 명령어
    # ──────────────────────────────────────────────
    async def _handle_shell(self, command: str) -> str:
        project_path = self.current_project.get("path", "~")
        result = await self.shell_ops.run(command, cwd=project_path)
        return self.shell_ops.format_result(result)

    # ──────────────────────────────────────────────
    # 프로젝트 전환
    # ──────────────────────────────────────────────
    def _switch_project(self, name: str) -> str:
        if name not in self.projects:
            return f"⚠️ 프로젝트 `{name}` 을 찾을 수 없습니다."
        self.current_project_name = name
        self.current_project = self.projects[name]
        self.brain.memory.clear()
        desc = self.current_project.get("description", "")
        return f"✅ 프로젝트 전환: *{name}*\n_{desc}_\n대화 메모리 초기화됨."

    # ──────────────────────────────────────────────
    # 상태 정보
    # ──────────────────────────────────────────────
    def get_status_text(self) -> str:
        ai = self.brain.get_status()
        proj = self.current_project_name or "없음"
        model = self.brain.model
        turns = self.brain.memory.turn_count

        # VRAM
        try:
            import subprocess
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            gpu_line = r.stdout.strip() if r.returncode == 0 else "N/A"
        except Exception:
            gpu_line = "N/A"

        ollama_status = "✅ 연결됨" if ai["ok"] else f"❌ 오류: {ai.get('error', '')}"
        models_str = ", ".join(ai.get("models", [])) if ai.get("models") else "-"

        return (
            f"🖥️ *시스템 상태*\n"
            f"GPU: `{gpu_line}`\n"
            f"Ollama: {ollama_status}\n"
            f"모델 목록: `{models_str}`\n\n"
            f"🤖 *에이전트 상태*\n"
            f"현재 모델: `{model}`\n"
            f"현재 프로젝트: `{proj}`\n"
            f"대화 턴 수: {turns}"
        )
