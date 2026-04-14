#!/usr/bin/env bash
# INSTALL-001: Telegram AI 에이전트 자동 설치 스크립트
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="telegram-agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="$(which python3)"
BOT_SCRIPT="${SCRIPT_DIR}/telegram-agent.py"

echo "============================================"
echo " Telegram AI 에이전트 설치"
echo "============================================"

# ── STEP 1: Python 버전 확인 ──────────────────────────────────────────────────
echo "[1/5] Python 버전 확인..."
PY_VER=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER 확인됨"
if [[ "$(echo "$PY_VER < 3.10" | bc -l)" == "1" ]]; then
    echo "  ⚠️  Python 3.10 이상이 필요합니다."
    exit 1
fi

# ── STEP 2: pip 패키지 설치 ──────────────────────────────────────────────────
echo "[2/5] 패키지 설치..."
$PYTHON_BIN -m pip install --quiet -r "${SCRIPT_DIR}/requirements.txt"
echo "  ✅ 패키지 설치 완료"

# ── STEP 3: Ollama 연결 확인 ──────────────────────────────────────────────────
echo "[3/5] Ollama 연결 확인..."
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✅ Ollama 연결 확인됨"
else
    echo "  ⚠️  Ollama 가 실행되지 않고 있습니다. 먼저 'ollama serve' 를 실행하세요."
fi

# ── STEP 4: .env 파일 확인 ────────────────────────────────────────────────────
echo "[4/5] 환경 설정 확인..."
if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
    if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
        cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
        echo "  ⚠️  .env 파일을 생성했습니다."
        echo "  ✏️   ${SCRIPT_DIR}/.env 파일을 편집하여 TELEGRAM_BOT_TOKEN 을 설정하세요:"
        echo "       TELEGRAM_BOT_TOKEN=your_token_here"
        echo "       ALLOWED_USER_ID=your_telegram_user_id"
    else
        echo "  ⚠️  .env 파일이 없습니다. .env 파일을 직접 생성하세요."
    fi
else
    echo "  ✅ .env 파일 확인됨"
fi

# ── STEP 5: systemd 서비스 등록 ───────────────────────────────────────────────
echo "[5/5] systemd 서비스 등록..."

# 실행 권한 부여
chmod +x "${BOT_SCRIPT}"

# 서비스 파일 작성
sudo tee "${SERVICE_FILE}" > /dev/null << EOF
[Unit]
Description=Telegram AI Agent (Gemma4)
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${SCRIPT_DIR}/.env
ExecStart=${PYTHON_BIN} ${BOT_SCRIPT}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
echo "  ✅ systemd 서비스 등록 완료: ${SERVICE_NAME}"

echo ""
echo "============================================"
echo " 설치 완료!"
echo "============================================"
echo ""
echo "실행 명령어:"
echo "  수동 실행:   cd ${SCRIPT_DIR} && python3 telegram-agent.py"
echo "  서비스 시작: sudo systemctl start ${SERVICE_NAME}"
echo "  서비스 상태: sudo systemctl status ${SERVICE_NAME}"
echo "  로그 확인:   sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo ".env 파일을 아직 설정하지 않았다면 먼저 설정하세요:"
echo "  ${SCRIPT_DIR}/.env"
