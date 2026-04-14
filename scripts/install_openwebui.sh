#!/bin/bash

# ============================================================
#  Open WebUI 설치 스크립트
#  Ubuntu 22.04 + Ollama 연동 (Docker 불필요)
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}${BOLD}[$1]${NC} $2"; }
print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
print_info() { echo -e "  ${CYAN}→${NC} $1"; }
print_err()  { echo -e "  ${RED}✗${NC} $1"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Open WebUI 설치 스크립트            ║${NC}"
echo -e "${BOLD}║   Ubuntu 22.04 + Ollama 연동             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Ollama 실행 확인 ──────────────────────────────────────
print_step "1/4" "Ollama 상태 확인"

if curl -s http://localhost:11434 &>/dev/null; then
    print_ok "Ollama 실행 중 (localhost:11434)"
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c \
        "import sys,json; [print('  •', m['name']) for m in json.load(sys.stdin)['models']]" 2>/dev/null)
    print_ok "설치된 모델:"
    echo "$MODELS"
else
    print_warn "Ollama가 실행 중이지 않습니다"
    print_info "Ollama 시작 중..."
    sudo systemctl start ollama || ollama serve &
    sleep 3
    if curl -s http://localhost:11434 &>/dev/null; then
        print_ok "Ollama 시작 완료"
    else
        print_err "Ollama 시작 실패 → 먼저 Ollama를 설치하세요"
        exit 1
    fi
fi

# ── 2. 설치 방법 선택 ────────────────────────────────────────
print_step "2/4" "설치 방법 선택"
echo ""
echo -e "  ${BOLD}1${NC}  pip (Python) — 가장 가볍고 빠름 ${GREEN}(권장)${NC}"
echo -e "  ${BOLD}2${NC}  uvx           — pip보다 격리된 환경"
echo -e "  ${BOLD}3${NC}  Docker        — 가장 안정적, Docker 필요"
echo ""
echo -e "  선택 [1/2/3, 기본값=1]: \c"
read -r METHOD
METHOD=${METHOD:-1}

# ── 3. 설치 ─────────────────────────────────────────────────
print_step "3/4" "Open WebUI 설치"

case $METHOD in
    1)
        # ── pip 설치 ──────────────────────────────────────
        print_info "pip으로 설치 중..."

        # Python 버전 확인
        PYTHON_VER=$(python3 --version 2>/dev/null | awk '{print $2}')
        print_ok "Python: $PYTHON_VER"

        # 가상환경 생성
        print_info "가상환경 생성: ~/open-webui-env"
        python3 -m venv ~/open-webui-env
        source ~/open-webui-env/bin/activate

        # Open WebUI 설치
        print_info "Open WebUI 설치 중... (수 분 소요)"
        pip install open-webui --quiet

        print_ok "설치 완료"

        # systemd 서비스 등록
        print_info "systemd 서비스 등록 중..."
        PYTHON_PATH=$(which python3)
        OPENWEBUI_PATH=$(which open-webui 2>/dev/null || echo "$HOME/open-webui-env/bin/open-webui")

        sudo tee /etc/systemd/system/open-webui.service > /dev/null << EOF
[Unit]
Description=Open WebUI
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
Environment="OLLAMA_BASE_URL=http://localhost:11434"
Environment="DATA_DIR=$HOME/.open-webui"
Environment="PATH=$HOME/open-webui-env/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$HOME/open-webui-env/bin/open-webui serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
        ;;

    2)
        # ── uvx 설치 ──────────────────────────────────────
        print_info "uv 설치 중..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        print_ok "uv 설치 완료"

        print_info "Open WebUI 설치 중..."
        DATA_DIR=~/.open-webui uvx --python 3.11 open-webui@latest serve &
        WEBUI_PID=$!
        sleep 5

        print_ok "설치 완료 (PID: $WEBUI_PID)"

        # systemd 서비스 등록
        UV_PATH=$(which uvx)
        sudo tee /etc/systemd/system/open-webui.service > /dev/null << EOF
[Unit]
Description=Open WebUI
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
Environment="DATA_DIR=$HOME/.open-webui"
Environment="OLLAMA_BASE_URL=http://localhost:11434"
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$UV_PATH --python 3.11 open-webui@latest serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        ;;

    3)
        # ── Docker 설치 ───────────────────────────────────
        if ! command -v docker &>/dev/null; then
            print_info "Docker 설치 중..."
            curl -fsSL https://get.docker.com | sh
            sudo usermod -aG docker $USER
            print_warn "Docker 그룹 적용을 위해 로그아웃 후 재로그인 필요"
        else
            print_ok "Docker 이미 설치됨"
        fi

        print_info "Open WebUI 컨테이너 시작 중..."
        docker run -d \
            --network host \
            --restart always \
            -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
            -v open-webui:/app/backend/data \
            --name open-webui \
            ghcr.io/open-webui/open-webui:main

        print_ok "Docker 컨테이너 시작 완료"
        echo ""
        echo -e "  ${GREEN}브라우저에서 접속: http://localhost:8080${NC}"
        exit 0
        ;;
esac

# ── 4. 서비스 시작 ───────────────────────────────────────────
print_step "4/4" "서비스 시작"

if [[ "$METHOD" != "2" ]]; then
    sudo systemctl daemon-reload
    sudo systemctl enable open-webui
    sudo systemctl start open-webui
    sleep 5

    if systemctl is-active --quiet open-webui; then
        print_ok "Open WebUI 서비스 시작 완료"
    else
        print_warn "서비스 시작 실패 → 수동으로 실행합니다"
        source ~/open-webui-env/bin/activate
        OLLAMA_BASE_URL=http://localhost:11434 \
        DATA_DIR=~/.open-webui \
        open-webui serve &
        sleep 5
    fi
fi

# ── 완료 ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║           설치 완료!                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}접속 주소:${NC}  ${CYAN}http://localhost:8080${NC}"
echo ""
echo -e "  ${BOLD}첫 실행 시:${NC}"
echo -e "  1. 브라우저에서 http://localhost:8080 접속"
echo -e "  2. 관리자 계정 생성 (첫 번째 계정이 관리자)"
echo -e "  3. 좌측 모델 선택 → gemma4:e4b / gemma4:26b 선택"
echo -e "  4. 채팅 시작!"
echo ""
echo -e "  ${BOLD}서비스 관리:${NC}"
echo -e "  ${CYAN}sudo systemctl status open-webui${NC}   # 상태"
echo -e "  ${CYAN}sudo systemctl restart open-webui${NC}  # 재시작"
echo -e "  ${CYAN}sudo systemctl stop open-webui${NC}     # 중지"
echo ""
echo -e "  ${BOLD}로그 확인:${NC}"
echo -e "  ${CYAN}journalctl -u open-webui -f${NC}"
echo ""

# 브라우저 자동 열기
echo -e "  브라우저를 자동으로 열까요? [y/N]: \c"
read -r OPEN_BROWSER
if [[ $OPEN_BROWSER =~ ^[Yy]$ ]]; then
    xdg-open http://localhost:8080 2>/dev/null &
    print_ok "브라우저 열기 완료"
fi
