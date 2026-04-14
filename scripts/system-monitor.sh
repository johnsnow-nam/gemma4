#!/usr/bin/env bash
# system-monitor 실행 스크립트
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT_DIR/system-monitor/.venv"

# venv 없으면 생성
if [ ! -f "$VENV/bin/python" ]; then
    echo "[system-monitor] 가상환경 생성 중..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q fastapi uvicorn psutil pynvml requests
fi

exec "$VENV/bin/python" "$ROOT_DIR/system-monitor/monitor.py" "$@"
