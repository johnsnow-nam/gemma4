#!/usr/bin/env bash
# system-monitor 자동 설치
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  AI System Monitor 설치${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. venv 생성
echo -e "${YELLOW}[1/4] 가상환경 생성...${NC}"
cd "$SCRIPT_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q fastapi uvicorn psutil pynvml requests
echo -e "${GREEN}✔ 패키지 설치 완료${NC}"

# 2. sudoers (systemctl 제어)
echo -e "${YELLOW}[2/4] sudo 설정 (systemctl 제어)...${NC}"
SUDOERS_FILE="/etc/sudoers.d/ai-monitor-control"
SUDOERS_CONTENT="$USER ALL=(ALL) NOPASSWD: /bin/systemctl start *, /bin/systemctl stop *, /bin/systemctl restart *"
echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 440 "$SUDOERS_FILE"
echo -e "${GREEN}✔ sudoers 설정 완료${NC}"

# 3. systemd 서비스 등록
echo -e "${YELLOW}[3/4] systemd 서비스 등록...${NC}"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
sudo tee /etc/systemd/system/system-monitor.service > /dev/null << EOF
[Unit]
Description=AI System Monitor Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_BIN $SCRIPT_DIR/monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable system-monitor
sudo systemctl start system-monitor
echo -e "${GREEN}✔ systemd 등록 및 시작 완료${NC}"

# 4. ~/.local/bin 심볼릭 링크
echo -e "${YELLOW}[4/4] 실행 스크립트 등록...${NC}"
LINK_SH="$SCRIPT_DIR/../scripts/system-monitor.sh"
cat > "$LINK_SH" << 'SHEOF'
#!/usr/bin/env bash
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$ROOT_DIR/system-monitor/.venv/bin/python"
exec "$PYTHON" "$ROOT_DIR/system-monitor/monitor.py" "$@"
SHEOF
chmod +x "$LINK_SH"
ln -sf "$LINK_SH" "$HOME/.local/bin/system-monitor" 2>/dev/null || true
echo -e "${GREEN}✔ system-monitor 명령 등록 완료${NC}"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  설치 완료!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  브라우저: ${CYAN}http://localhost:9090${NC}"
echo -e "  상태 확인: ${YELLOW}systemctl status system-monitor${NC}"
echo -e "  로그: ${YELLOW}journalctl -u system-monitor -f${NC}"
