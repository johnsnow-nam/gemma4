#!/usr/bin/env bash
# telegram-agent 실행 스크립트 (가상환경 자동 활성화)
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
PROJ_DIR="$(cd "$(dirname "$REAL_SCRIPT")/.." && pwd)"
VENV="$PROJ_DIR/telegram-agent/.venv"
SCRIPT="$PROJ_DIR/telegram-agent/telegram-agent.py"

if [[ ! -d "$VENV" ]]; then
    echo "⚠️  가상환경이 없습니다. 설치를 진행합니다..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet -r "$PROJ_DIR/telegram-agent/requirements.txt"
    echo "✅ 설치 완료"
fi

# .env 파일 로드
if [[ -f "$PROJ_DIR/telegram-agent/.env" ]]; then
    set -a
    source "$PROJ_DIR/telegram-agent/.env"
    set +a
elif [[ ! -f "$PROJ_DIR/telegram-agent/.env" ]]; then
    echo "⚠️  .env 파일이 없습니다: $PROJ_DIR/telegram-agent/.env"
    echo "   cp $PROJ_DIR/telegram-agent/.env.example $PROJ_DIR/telegram-agent/.env"
    echo "   위 명령으로 생성 후 TELEGRAM_BOT_TOKEN을 설정하세요."
    exit 1
fi

exec "$VENV/bin/python" "$SCRIPT" "$@"
