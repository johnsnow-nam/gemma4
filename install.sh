#!/usr/bin/env bash
# =============================================================
#  Gemma AI 설치 스크립트 (Mac / Linux)
#  사용법: curl -sSL https://raw.githubusercontent.com/johnsnow-nam/gemma4/master/install.sh | bash
# =============================================================
set -e

REPO_URL="https://github.com/johnsnow-nam/gemma4.git"
INSTALL_DIR="$HOME/gemma4"
MODEL="gemma4:e4b"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

info()    { echo -e "${BLUE}[Gemma AI]${NC} $1"; }
success() { echo -e "${GREEN}[완료]${NC} $1"; }
warn()    { echo -e "${YELLOW}[주의]${NC} $1"; }
error()   { echo -e "${RED}[오류]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       🤖  Gemma AI 설치 시작         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Ollama 확인 ────────────────────────────────────────────
info "Ollama 확인 중..."
if ! command -v ollama &>/dev/null; then
  error "Ollama가 설치되지 않았습니다.\nhttps://ollama.com/download 에서 먼저 설치해 주세요."
fi
success "Ollama 확인됨 ($(ollama --version))"

# ── 2. Python 확인 ───────────────────────────────────────────
info "Python 확인 중..."
PYTHON=""
for cmd in python3 python; do
  if command -v $cmd &>/dev/null; then
    VER=$($cmd -c "import sys; print(sys.version_info[:2])")
    if $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"; then
      PYTHON=$cmd; break
    fi
  fi
done
[ -z "$PYTHON" ] && error "Python 3.9 이상이 필요합니다.\nhttps://www.python.org/downloads/ 에서 설치해 주세요."
success "Python 확인됨 ($PYTHON)"

# ── 3. Git 확인 ──────────────────────────────────────────────
info "Git 확인 중..."
command -v git &>/dev/null || error "Git이 설치되지 않았습니다.\nhttps://git-scm.com/downloads 에서 설치해 주세요."
success "Git 확인됨"

# ── 4. 소스코드 다운로드 ─────────────────────────────────────
info "Gemma AI 소스코드 다운로드 중..."
if [ -d "$INSTALL_DIR/.git" ]; then
  warn "이미 설치되어 있습니다. 최신 버전으로 업데이트합니다."
  git -C "$INSTALL_DIR" pull --quiet
else
  git clone --quiet "$REPO_URL" "$INSTALL_DIR"
fi
success "소스코드 준비 완료 → $INSTALL_DIR"

# ── 5. Python 가상환경 + Open WebUI 설치 ─────────────────────
info "Open WebUI 설치 중... (1~3분 소요)"
cd "$INSTALL_DIR"
$PYTHON -m venv .venv-webui --quiet
.venv-webui/bin/pip install --quiet --upgrade pip
.venv-webui/bin/pip install --quiet open-webui
success "Open WebUI 설치 완료"

# ── 6. AI 모델 다운로드 ──────────────────────────────────────
info "AI 모델 다운로드 중: $MODEL (5~10분 소요, 처음 한 번만)"
ollama list 2>/dev/null | grep -q "${MODEL%:*}" && \
  success "모델이 이미 있습니다: $MODEL" || \
  ollama pull "$MODEL"
success "모델 준비 완료"

# ── 7. 실행 스크립트 생성 ────────────────────────────────────
info "실행 스크립트 생성 중..."
cat > "$INSTALL_DIR/start.sh" << 'LAUNCHER'
#!/usr/bin/env bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🤖 Gemma AI 시작 중..."

# Ollama 백그라운드 실행
if ! pgrep -x "ollama" > /dev/null; then
  ollama serve &>/dev/null &
  sleep 2
fi

# 브라우저 열기 (3초 후)
(sleep 3 && (open "http://localhost:8080" 2>/dev/null || xdg-open "http://localhost:8080" 2>/dev/null)) &

# Open WebUI 실행
OLLAMA_API_BASE_URL=http://localhost:11434 \
  "$INSTALL_DIR/.venv-webui/bin/open-webui" serve --port 8080
LAUNCHER
chmod +x "$INSTALL_DIR/start.sh"

# ── 8. 바탕화면 바로가기 ─────────────────────────────────────
DESKTOP="$HOME/Desktop"
if [ -d "$DESKTOP" ]; then
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    cat > "$DESKTOP/Gemma AI.desktop" << EOF
[Desktop Entry]
Name=Gemma AI
Comment=로컬 AI 채팅
Exec=bash $INSTALL_DIR/start.sh
Icon=utilities-terminal
Terminal=true
Type=Application
EOF
    chmod +x "$DESKTOP/Gemma AI.desktop"
    success "바탕화면 바로가기 생성됨 (Linux)"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    cat > "$DESKTOP/Gemma AI.command" << EOF
#!/bin/bash
bash "$INSTALL_DIR/start.sh"
EOF
    chmod +x "$DESKTOP/Gemma AI.command"
    success "바탕화면 바로가기 생성됨 (Mac)"
  fi
fi

# ── 완료 ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║     🎉  설치 완료!                   ║"
echo "╠══════════════════════════════════════╣"
echo "║  실행 방법:                          ║"
echo "║  1. 바탕화면 'Gemma AI' 더블클릭     ║"
echo "║  2. 또는 터미널에서:                 ║"
echo "║     bash ~/gemma4/start.sh           ║"
echo "╚══════════════════════════════════════╝"
echo ""
