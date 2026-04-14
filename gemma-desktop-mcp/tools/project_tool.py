"""T-009, T-010, T-011: 검색 / 시스템 정보 / 모델 목록"""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path

from config.settings import MAX_SEARCH_RESULTS, OLLAMA_URL


def search_files(
    path: str,
    query: str,
    pattern: str = "*",
    use_regex: bool = False,
    max_results: int = MAX_SEARCH_RESULTS,
) -> str:
    """T-009: 폴더 내 파일에서 텍스트 검색"""
    root = Path(os.path.expanduser(path))
    if not root.exists():
        return f"[오류] 경로 없음: {path}"

    EXCLUDE_DIRS = {"node_modules", ".git", "build", "__pycache__", ".venv", "dist"}

    results: list[str] = []
    count = 0

    try:
        search_pat = re.compile(query, re.IGNORECASE) if use_regex else None
    except re.error as e:
        return f"[오류] 잘못된 정규식: {e}"

    def _matches(text: str) -> list[tuple[int, str]]:
        hits = []
        for i, line in enumerate(text.splitlines(), 1):
            if search_pat:
                if search_pat.search(line):
                    hits.append((i, line))
            else:
                if query.lower() in line.lower():
                    hits.append((i, line))
        return hits

    for p in sorted(root.rglob(pattern)):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        try:
            with open(p, "rb") as f:
                if b"\x00" in f.read(8192):
                    continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        hits = _matches(text)
        if hits:
            rel = p.relative_to(root)
            results.append(f"**{rel}** ({len(hits)}개 일치)")
            for lineno, line in hits[:5]:
                results.append(f"  L{lineno}: {line.strip()[:120]}")
            if len(hits) > 5:
                results.append(f"  ... 외 {len(hits) - 5}개")
            count += len(hits)
            if len(results) > max_results:
                results.append(f"\n[최대 결과 수 초과, {max_results}개 이후 생략]")
                break

    if not results:
        return f"검색 결과 없음: '{query}' in {path}"
    return f"검색: '{query}'  경로: {path}\n총 {count}개 일치\n\n" + "\n".join(results)


def get_system_info() -> str:
    """T-010: GPU, VRAM, 모델 상태 등 시스템 정보"""
    import shutil
    lines = ["## 시스템 정보"]

    # GPU / VRAM
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            for gpu_line in r.stdout.strip().splitlines():
                parts = [p.strip() for p in gpu_line.split(",")]
                if len(parts) >= 5:
                    name, used, total, util, temp = parts[:5]
                    pct = int(used) / int(total) * 100
                    lines.append(
                        f"GPU: {name}  VRAM: {used}/{total}MB ({pct:.0f}%)  "
                        f"이용률: {util}%  온도: {temp}°C"
                    )
    except Exception:
        lines.append("GPU: nvidia-smi 없음")

    # CPU / RAM
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        lines.append(f"CPU: {cpu:.1f}%  RAM: {mem.used//1024//1024}/{mem.total//1024//1024} MB ({mem.percent:.0f}%)")
    except ImportError:
        try:
            r = subprocess.run(["free", "-m"], capture_output=True, text=True)
            lines.append(f"RAM:\n{r.stdout.strip()}")
        except Exception:
            lines.append("CPU/RAM: psutil 없음")

    # 디스크
    try:
        total_b, used_b, free_b = shutil.disk_usage("/")
        lines.append(
            f"디스크(/): {used_b//1024//1024//1024}/{total_b//1024//1024//1024} GB "
            f"(여유: {free_b//1024//1024//1024} GB)"
        )
    except Exception:
        pass

    # Ollama 모델
    try:
        import ollama
        client = ollama.Client(host=OLLAMA_URL)
        resp = client.list()
        models = resp.get("models", [])
        if models:
            lines.append(f"\nOllama 모델 ({len(models)}개):")
            for m in models:
                name = m.get("name", "?")
                size = m.get("size", 0) / 1e9
                lines.append(f"  - {name}  ({size:.1f} GB)")
        else:
            lines.append("Ollama 모델: 없음")
    except Exception as e:
        lines.append(f"Ollama: 연결 실패 ({e})")

    return "\n".join(lines)


def list_ollama_models() -> str:
    """T-011: Ollama 모델 목록 (포맷된 텍스트)"""
    try:
        import ollama
        client = ollama.Client(host=OLLAMA_URL)
        resp = client.list()
        models = resp.get("models", [])
    except Exception as e:
        return f"[오류] Ollama 연결 실패: {e}"

    if not models:
        return "설치된 Ollama 모델이 없습니다."

    lines = [f"## Ollama 모델 목록 ({len(models)}개)\n"]
    for m in models:
        name = m.get("name", "?")
        size_gb = m.get("size", 0) / 1e9
        modified = m.get("modified_at", "")[:10] if m.get("modified_at") else "-"
        details = m.get("details", {})
        quant = details.get("quantization_level", "-")
        family = details.get("family", "-")
        lines.append(
            f"  **{name}**  크기: {size_gb:.1f} GB  퀀타이제이션: {quant}  "
            f"계열: {family}  수정: {modified}"
        )

    return "\n".join(lines)
