#!/usr/bin/env bash
# gemma-desktop-mcp 서버 실행 스크립트 (가상환경 자동 활성화)
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
PROJ_DIR="$(cd "$(dirname "$REAL_SCRIPT")/.." && pwd)"
VENV="$PROJ_DIR/gemma-desktop-mcp/.venv"
SCRIPT="$PROJ_DIR/gemma-desktop-mcp/gemma-mcp-server.py"

if [[ ! -d "$VENV" ]]; then
    echo "⚠️  가상환경이 없습니다. 설치를 진행합니다..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet -r "$PROJ_DIR/gemma-desktop-mcp/requirements.txt"
    echo "✅ 설치 완료"
fi

exec "$VENV/bin/python" "$SCRIPT" "$@"
