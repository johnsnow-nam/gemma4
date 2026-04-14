"""슬래시 명령어 처리 — 전체 구현"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class CommandResult:
    handled: bool
    output: str = ""
    quit: bool = False
    clear_session: bool = False
    model_changed: str | None = None
    # 추가 액션 플래그
    needs_ai: bool = False          # AI 응답이 필요한 경우
    ai_prompt: str = ""             # AI에 보낼 프롬프트
    retry: bool = False             # /retry 플래그
    compress: bool = False          # /compress 플래그
    watch_file: str = ""            # /watch 대상 파일
    verbose_toggle: bool = False    # /verbose 토글
    extra: dict = field(default_factory=dict)


class SlashCommandHandler:
    def __init__(self, session, ollama_client):
        self.session = session
        self.client = ollama_client
        self._verbose: bool = False
        self._last_response: str = ""  # /copy, /retry용
        self._settings = None
        self._profile: dict | None = None

    def _get_settings(self):
        if self._settings is None:
            from config.settings import get_settings
            self._settings = get_settings()
        return self._settings

    def set_last_response(self, response: str) -> None:
        self._last_response = response

    def get_verbose(self) -> bool:
        return self._verbose

    def handle(self, raw: str) -> CommandResult:
        parts = raw.strip().split()
        if not parts:
            return CommandResult(handled=False)

        cmd = parts[0].lower()
        args = parts[1:]

        # /copy code 처리
        if cmd == "/copy" and args and args[0].lower() == "code":
            return self._copy_code([])

        dispatch = {
            "/help":       self._help,
            "/clear":      self._clear,
            "/model":      self._model,
            "/models":     self._models,
            "/save":       self._save,
            "/load":       self._load,
            "/sessions":   self._sessions,
            "/tokens":     self._tokens,
            "/retry":      self._retry,
            "/compress":   self._compress,
            "/copy":       self._copy,
            "/ls":         self._ls,
            "/exit":       self._exit,
            "/quit":       self._exit,
            "/run":        self._run,
            "/diff":       self._diff,
            "/commit":     self._commit,
            "/watch":      self._watch,
            "/screenshot": self._screenshot,
            "/set":        self._set,
            "/config":     self._config,
            "/profile":    self._profile_cmd,
            "/profiles":   self._profiles,
            "/verbose":    self._verbose_cmd,
        }

        handler = dispatch.get(cmd)
        if handler is None:
            return CommandResult(handled=False)
        return handler(args)

    # ------------------------------------------------------------------
    # 도움말
    # ------------------------------------------------------------------
    def _help(self, args) -> CommandResult:
        text = """[bold cyan]gemma-cli 슬래시 명령어[/bold cyan]

[yellow]대화 관리[/yellow]
  /clear              대화 초기화
  /retry              마지막 응답 재생성
  /compress           이전 대화 요약으로 압축
  /tokens             토큰 사용량 표시
  /save [이름]         세션 저장
  /load [이름]         세션 불러오기
  /sessions           저장된 세션 목록
  /copy               마지막 응답 클립보드 복사
  /copy code          마지막 응답의 코드블록만 복사

[yellow]모델 / 설정[/yellow]
  /model [이름]        모델 전환 (예: /model gemma4:e4b)
  /models             사용 가능한 모델 목록
  /set [키] [값]       설정 변경 (temperature, num_ctx, top_p, repeat_penalty)
  /config show        현재 설정 확인
  /config set [키] [값] 설정 저장
  /config reset       설정 초기화

[yellow]프로파일[/yellow]
  /profile            현재 프로파일 정보
  /profile create [이름]  새 프로파일 생성 (대화형)
  /profile load [이름]    프로파일 로드
  /profiles           프로파일 목록

[yellow]파일[/yellow]
  @파일경로            파일 읽기 (예: @main.c)
  @src/**/*.c         Glob 패턴 읽기
  @폴더/              폴더 전체 읽기
  @이미지.png          이미지 분석

[yellow]실행[/yellow]
  /run @파일           파일 실행 (Python/Bash/C/Node)
  /screenshot         스크린샷 촬영 후 분석

[yellow]셸[/yellow]
  !명령어              셸 명령어 실행 (예: !ls -la)

[yellow]Git[/yellow]
  /diff               git diff를 AI에게 리뷰 요청
  /commit             staged 변경사항 커밋 메시지 생성

[yellow]기타[/yellow]
  /watch @파일         파일 변경 감지
  /verbose            API 상세 출력 토글
  /ls                 현재 폴더 목록
  /help               이 도움말
  /exit               종료"""
        return CommandResult(handled=True, output=text)

    # ------------------------------------------------------------------
    # 대화 관리
    # ------------------------------------------------------------------
    def _clear(self, args) -> CommandResult:
        self.session.clear()
        return CommandResult(handled=True, output="[green]대화가 초기화됐습니다.[/green]", clear_session=True)

    def _retry(self, args) -> CommandResult:
        msgs = self.session.messages
        if msgs and msgs[-1]["role"] == "assistant":
            self.session.messages = msgs[:-1]
        return CommandResult(handled=True, output="[yellow]마지막 응답을 다시 생성합니다...[/yellow]", retry=True)

    def _compress(self, args) -> CommandResult:
        """D-005: 이전 대화를 AI가 요약"""
        msgs = self.session.messages
        user_msgs = [m for m in msgs if m["role"] != "system"]
        if len(user_msgs) < 2:
            return CommandResult(handled=True, output="[yellow]압축할 대화가 충분하지 않습니다.[/yellow]")
        return CommandResult(handled=True, compress=True, output="[dim]대화를 요약하는 중...[/dim]")

    def _copy(self, args) -> CommandResult:
        """U-005: 마지막 AI 응답 클립보드 복사"""
        if not self._last_response:
            return CommandResult(handled=True, output="[yellow]복사할 응답이 없습니다.[/yellow]")
        success = _copy_to_clipboard(self._last_response)
        if success:
            return CommandResult(handled=True, output="[green]클립보드에 복사됐습니다.[/green]")
        return CommandResult(handled=True, output="[red]클립보드 복사 실패 (xclip/xsel/wl-copy 설치 필요)[/red]")

    def _copy_code(self, args) -> CommandResult:
        """U-005: 마지막 응답의 코드블록만 복사"""
        if not self._last_response:
            return CommandResult(handled=True, output="[yellow]복사할 응답이 없습니다.[/yellow]")
        from core.file_handler import extract_code_blocks
        blocks = extract_code_blocks(self._last_response)
        if not blocks:
            return CommandResult(handled=True, output="[yellow]코드블록이 없습니다.[/yellow]")
        code = "\n\n".join(b["code"] for b in blocks)
        success = _copy_to_clipboard(code)
        if success:
            return CommandResult(handled=True, output=f"[green]코드블록 {len(blocks)}개를 클립보드에 복사했습니다.[/green]")
        return CommandResult(handled=True, output="[red]클립보드 복사 실패[/red]")

    def _tokens(self, args) -> CommandResult:
        settings = self._get_settings()
        ctx = settings.num_ctx
        est = self.session.token_estimate()
        pct = est / ctx * 100
        color = "green" if pct < 80 else ("yellow" if pct < 95 else "red")
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines = [
            "[bold]토큰 사용량[/bold]",
            f"  [{color}]{bar}[/{color}] {est:,} / {ctx:,} ({pct:.1f}%)",
            f"  메시지: {len(self.session.messages)}개",
        ]
        if pct >= 95:
            lines.append("  [red]컨텍스트 한도에 거의 도달했습니다. /compress 를 권장합니다.[/red]")
        elif pct >= 80:
            lines.append("  [yellow]컨텍스트가 80% 이상 사용됐습니다.[/yellow]")
        return CommandResult(handled=True, output="\n".join(lines))

    # ------------------------------------------------------------------
    # 세션
    # ------------------------------------------------------------------
    def _save(self, args) -> CommandResult:
        name = args[0] if args else "default"
        path = self.session.save(name)
        return CommandResult(handled=True, output=f"[green]세션 저장: {path}[/green]")

    def _load(self, args) -> CommandResult:
        if not args:
            return CommandResult(handled=True, output="[red]세션 이름을 지정하세요: /load [이름][/red]")
        name = args[0]
        try:
            from core.session import Session
            new_session = Session.load(name)
            self.session.messages = new_session.messages
            self.session.model = new_session.model
            self.client.model = new_session.model
            return CommandResult(
                handled=True,
                output=f"[green]세션 불러옴: [cyan]{name}[/cyan] (메시지 {len(new_session.messages)}개)[/green]",
            )
        except FileNotFoundError as e:
            return CommandResult(handled=True, output=f"[red]{e}[/red]")

    def _sessions(self, args) -> CommandResult:
        from core.session import Session
        sessions = Session.list_sessions()
        if not sessions:
            return CommandResult(handled=True, output="저장된 세션이 없습니다.")
        lines = ["[bold]저장된 세션:[/bold]"] + [f"  [cyan]{s}[/cyan]" for s in sessions]
        return CommandResult(handled=True, output="\n".join(lines))

    # ------------------------------------------------------------------
    # 모델
    # ------------------------------------------------------------------
    def _model(self, args) -> CommandResult:
        if not args:
            return CommandResult(handled=True, output=f"현재 모델: [cyan]{self.client.model}[/cyan]")
        new_model = args[0]
        self.client.model = new_model
        self.session.model = new_model
        return CommandResult(
            handled=True,
            output=f"[green]모델을 [cyan]{new_model}[/cyan] 으로 전환했습니다.[/green]",
            model_changed=new_model,
        )

    def _models(self, args) -> CommandResult:
        models = self.client.list_models()
        if not models:
            return CommandResult(handled=True, output="[red]Ollama에서 모델 목록을 가져올 수 없습니다.[/red]")

        from utils.selector import select

        choices = []
        default_idx = 0
        for i, m in enumerate(models):
            name = m.get("name", "?")
            size_gb = m.get("size", 0) / 1e9
            marker = " ◀ 현재" if name == self.client.model else ""
            choices.append((name, f"{name}  ({size_gb:.1f} GB){marker}"))
            if name == self.client.model:
                default_idx = i

        selected = select("모델 선택", choices, default=default_idx)

        if selected is None or selected == self.client.model:
            return CommandResult(handled=True, output="[dim]모델 변경 없음.[/dim]")

        self.client.model = selected
        self.session.model = selected
        return CommandResult(
            handled=True,
            output=f"[green]모델 전환: [cyan]{selected}[/cyan][/green]",
            model_changed=selected,
        )

    # ------------------------------------------------------------------
    # M-004 /set
    # ------------------------------------------------------------------
    def _set(self, args) -> CommandResult:
        """M-004: temperature, num_ctx, top_p, repeat_penalty 조정"""
        valid_keys = {"temperature", "num_ctx", "top_p", "repeat_penalty"}
        if not args:
            settings = self._get_settings()
            lines = ["[bold]/set 사용 가능한 파라미터:[/bold]"]
            for k in sorted(valid_keys):
                lines.append(f"  [cyan]{k}[/cyan] = [yellow]{settings.get(k)}[/yellow]")
            lines.append("\n사용법: /set temperature 0.7")
            return CommandResult(handled=True, output="\n".join(lines))

        if len(args) < 2:
            return CommandResult(handled=True, output="[red]사용법: /set [키] [값][/red]")

        key, val_str = args[0], args[1]
        if key not in valid_keys:
            return CommandResult(handled=True, output=f"[red]알 수 없는 설정: {key}. 가능한 값: {', '.join(sorted(valid_keys))}[/red]")

        try:
            if key == "num_ctx":
                val = int(val_str)
            else:
                val = float(val_str)
        except ValueError:
            return CommandResult(handled=True, output=f"[red]유효하지 않은 값: {val_str}[/red]")

        # 클라이언트 설정 업데이트
        settings = self._get_settings()
        settings.set(key, val)
        setattr(self.client, key, val) if hasattr(self.client, key) else None
        return CommandResult(handled=True, output=f"[green]{key} = {val} 으로 설정됐습니다.[/green]")

    # ------------------------------------------------------------------
    # S-002 /config
    # ------------------------------------------------------------------
    def _config(self, args) -> CommandResult:
        settings = self._get_settings()
        if not args or args[0] == "show":
            return CommandResult(handled=True, output=settings.show())

        if args[0] == "set":
            if len(args) < 3:
                return CommandResult(handled=True, output="[red]사용법: /config set [키] [값][/red]")
            key, val_str = args[1], args[2]
            # 타입 자동 감지
            try:
                if val_str.lower() in {"true", "false"}:
                    val = val_str.lower() == "true"
                elif "." in val_str:
                    val = float(val_str)
                else:
                    val = int(val_str)
            except ValueError:
                val = val_str
            settings.set(key, val)
            return CommandResult(handled=True, output=f"[green]설정 저장: {key} = {val!r}[/green]")

        if args[0] == "reset":
            key = args[1] if len(args) > 1 else None
            settings.reset(key)
            if key:
                return CommandResult(handled=True, output=f"[green]{key} 초기화됐습니다.[/green]")
            return CommandResult(handled=True, output="[green]모든 설정이 초기화됐습니다.[/green]")

        return CommandResult(handled=True, output="[red]사용법: /config show | /config set [키] [값] | /config reset[/red]")

    # ------------------------------------------------------------------
    # P-001 / P-002 프로파일
    # ------------------------------------------------------------------
    def _profile_cmd(self, args) -> CommandResult:
        from config.profiles import (
            get_profile, create_profile, list_profiles, format_profile_info
        )

        if not args:
            # 현재 프로파일 표시
            if self._profile:
                return CommandResult(handled=True, output=format_profile_info(self._profile))
            return CommandResult(handled=True, output="[yellow]활성 프로파일 없음. /profile load [이름] 으로 로드하세요.[/yellow]")

        sub = args[0].lower()

        if sub == "load":
            if len(args) < 2:
                return CommandResult(handled=True, output="[red]사용법: /profile load [이름][/red]")
            name = args[1]
            profile = get_profile(name)
            if not profile:
                return CommandResult(handled=True, output=f"[red]프로파일을 찾을 수 없습니다: {name}[/red]")
            self._apply_profile(profile)
            return CommandResult(
                handled=True,
                output=f"[green]프로파일 로드됨: [cyan]{name}[/cyan][/green]\n{format_profile_info(profile)}",
            )

        if sub == "create":
            name = args[1] if len(args) > 1 else "custom"
            return CommandResult(
                handled=True,
                output=f"[yellow]프로파일 '{name}' 생성은 대화형 입력이 필요합니다. /profile create 후 프롬프트에 따라 입력하세요.[/yellow]",
                extra={"profile_create": name},
            )

        return CommandResult(handled=True, output="[red]사용법: /profile | /profile load [이름] | /profile create [이름][/red]")

    def _profiles(self, args) -> CommandResult:
        from config.profiles import list_profiles, get_profile, BUILTIN_PROFILES
        names = list_profiles()
        if not names:
            return CommandResult(handled=True, output="사용 가능한 프로파일이 없습니다.")
        lines = ["[bold]사용 가능한 프로파일:[/bold]"]
        for name in names:
            marker = " [dim](내장)[/dim]" if name in BUILTIN_PROFILES else " [dim](사용자)[/dim]"
            active = " [green]◀ 활성[/green]" if (self._profile and self._profile.get("name") == name) else ""
            p = get_profile(name)
            desc = p.get("description", "") if p else ""
            lines.append(f"  [cyan]{name}[/cyan]{marker}{active}  {desc}")
        return CommandResult(handled=True, output="\n".join(lines))

    def _apply_profile(self, profile: dict) -> None:
        """프로파일 설정 적용"""
        self._profile = profile
        if profile.get("model"):
            self.client.model = profile["model"]
            self.session.model = profile["model"]
        if profile.get("system_prompt"):
            # 시스템 메시지 업데이트
            msgs = self.session.messages
            if msgs and msgs[0]["role"] == "system":
                msgs[0]["content"] = profile["system_prompt"]
            else:
                msgs.insert(0, {"role": "system", "content": profile["system_prompt"]})

    # ------------------------------------------------------------------
    # C-001 /run
    # ------------------------------------------------------------------
    def _run(self, args) -> CommandResult:
        if not args:
            return CommandResult(handled=True, output="[red]사용법: /run @파일경로[/red]")

        file_ref = args[0]
        if file_ref.startswith("@"):
            file_ref = file_ref[1:]

        path = Path(os.path.expanduser(file_ref))
        if not path.exists():
            return CommandResult(handled=True, output=f"[red]파일을 찾을 수 없습니다: {file_ref}[/red]")

        from core.code_runner import run_file
        from rich.console import Console
        console = Console()
        console.print(f"[dim]실행 중: {path}[/dim]")

        stdout, stderr, elapsed = run_file(str(path))

        output_lines = [f"[bold]실행 결과: {path.name}[/bold]  [dim]({elapsed:.2f}초)[/dim]"]
        if stdout:
            output_lines.append(f"[dim]stdout:[/dim]\n{stdout}")
        if stderr:
            output_lines.append(f"[red][dim]stderr:[/dim]\n{stderr}[/red]")
        if not stdout and not stderr:
            output_lines.append("[dim](출력 없음)[/dim]")

        result_text = "\n".join(output_lines)

        # 결과를 다음 대화 컨텍스트에 포함
        context = f"파일 실행 결과 ({path.name}, {elapsed:.2f}초):\n"
        if stdout:
            context += f"stdout:\n```\n{stdout}\n```\n"
        if stderr:
            context += f"stderr:\n```\n{stderr}\n```\n"

        return CommandResult(
            handled=True,
            output=result_text,
            needs_ai=True,
            ai_prompt=f"{context}\n위 실행 결과에 대해 분석해줘.",
        )

    # ------------------------------------------------------------------
    # G-002 /diff
    # ------------------------------------------------------------------
    def _diff(self, args) -> CommandResult:
        from core.git_handler import get_diff, is_git_repo
        if not is_git_repo():
            return CommandResult(handled=True, output="[red]현재 디렉터리는 Git 저장소가 아닙니다.[/red]")

        staged = "--staged" in args or "-s" in args
        diff = get_diff(staged_only=staged)

        if not diff:
            msg = "스테이징된 변경사항이 없습니다." if staged else "변경사항이 없습니다."
            return CommandResult(handled=True, output=f"[yellow]{msg}[/yellow]")

        prompt = (
            f"다음 git diff를 리뷰해줘. 버그, 개선사항, 코드 품질 문제를 지적해줘:\n"
            f"```diff\n{diff[:6000]}\n```"
        )
        return CommandResult(
            handled=True,
            output=f"[dim]diff {len(diff)}자를 AI에게 전달합니다...[/dim]",
            needs_ai=True,
            ai_prompt=prompt,
        )

    # ------------------------------------------------------------------
    # G-003 /commit
    # ------------------------------------------------------------------
    def _commit(self, args) -> CommandResult:
        from core.git_handler import get_staged_diff, is_git_repo, generate_commit_message_prompt
        if not is_git_repo():
            return CommandResult(handled=True, output="[red]현재 디렉터리는 Git 저장소가 아닙니다.[/red]")

        diff = get_staged_diff()
        if not diff:
            return CommandResult(
                handled=True,
                output="[yellow]스테이징된 변경사항이 없습니다. `git add` 후 다시 시도하세요.[/yellow]"
            )

        prompt = generate_commit_message_prompt(diff)
        return CommandResult(
            handled=True,
            output="[dim]staged diff 분석 중...[/dim]",
            needs_ai=True,
            ai_prompt=prompt,
            extra={"commit_mode": True},
        )

    # ------------------------------------------------------------------
    # F-005 /watch
    # ------------------------------------------------------------------
    def _watch(self, args) -> CommandResult:
        if not args:
            return CommandResult(handled=True, output="[red]사용법: /watch @파일경로[/red]")
        file_ref = args[0]
        if file_ref.startswith("@"):
            file_ref = file_ref[1:]
        path = Path(os.path.expanduser(file_ref))
        if not path.exists():
            return CommandResult(handled=True, output=f"[red]파일을 찾을 수 없습니다: {file_ref}[/red]")
        return CommandResult(
            handled=True,
            output=f"[green]파일 감시 시작: [cyan]{path}[/cyan]  (변경 시 알림)[/green]",
            watch_file=str(path),
        )

    # ------------------------------------------------------------------
    # I-004 /screenshot
    # ------------------------------------------------------------------
    def _screenshot(self, args) -> CommandResult:
        from core.image_handler import take_screenshot
        from rich.console import Console
        Console().print("[dim]스크린샷 촬영 중...[/dim]")
        tmp = take_screenshot()
        if not tmp:
            return CommandResult(
                handled=True,
                output="[red]스크린샷 실패. scrot 또는 gnome-screenshot이 설치되어 있는지 확인하세요.[/red]"
            )
        return CommandResult(
            handled=True,
            output=f"[green]스크린샷: {tmp}[/green]",
            needs_ai=True,
            ai_prompt="이 스크린샷을 분석해줘.",
            extra={"screenshot_path": tmp},
        )

    # ------------------------------------------------------------------
    # V-001 /verbose
    # ------------------------------------------------------------------
    def _verbose_cmd(self, args) -> CommandResult:
        self._verbose = not self._verbose
        state = "[green]ON[/green]" if self._verbose else "[dim]OFF[/dim]"
        return CommandResult(handled=True, output=f"[bold]Verbose 모드: {state}[/bold]", verbose_toggle=True)

    # ------------------------------------------------------------------
    # /ls
    # ------------------------------------------------------------------
    def _ls(self, args) -> CommandResult:
        cwd = os.getcwd()
        try:
            entries = sorted(os.listdir(cwd))
            lines = [f"[bold]{cwd}[/bold]"]
            for e in entries:
                marker = "/" if os.path.isdir(os.path.join(cwd, e)) else ""
                lines.append(f"  {e}{marker}")
            return CommandResult(handled=True, output="\n".join(lines))
        except Exception as e:
            return CommandResult(handled=True, output=f"[red]{e}[/red]")

    # ------------------------------------------------------------------
    # /exit
    # ------------------------------------------------------------------
    def _exit(self, args) -> CommandResult:
        return CommandResult(handled=True, output="[yellow]종료합니다.[/yellow]", quit=True)


# ---------------------------------------------------------------------------
# 클립보드 유틸
# ---------------------------------------------------------------------------

def _copy_to_clipboard(text: str) -> bool:
    """텍스트를 클립보드에 복사 (Linux: xclip/xsel/wl-copy)"""
    # xclip
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode("utf-8"),
            capture_output=True, timeout=3
        )
        if r.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # xsel
    try:
        r = subprocess.run(
            ["xsel", "--clipboard", "--input"],
            input=text.encode("utf-8"),
            capture_output=True, timeout=3
        )
        if r.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # wl-copy (Wayland)
    try:
        r = subprocess.run(
            ["wl-copy"],
            input=text.encode("utf-8"),
            capture_output=True, timeout=3
        )
        if r.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return False
