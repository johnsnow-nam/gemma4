#!/bin/bash

# ============================================================
#  Ollama 설치 스크립트 for Ubuntu (RTX 5070 / CUDA 12.8)
#  작성: Claude
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
print_err()  { echo -e "  ${RED}✗${NC} $1"; }
print_info() { echo -e "  ${CYAN}→${NC} $1"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Ollama 설치 스크립트               ║${NC}"
echo -e "${BOLD}║   Ubuntu 22.04 + RTX 5070 + CUDA 12.8   ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. 시스템 환경 확인 ──────────────────────────────────────
print_step "1/5" "시스템 환경 확인"

OS=$(lsb_release -ds 2>/dev/null || echo "Unknown")
KERNEL=$(uname -r)
print_ok "OS: $OS"
print_ok "커널: $KERNEL"

# GPU 확인
if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    CUDA_VER=$(nvidia-smi | grep "CUDA Version" | awk '{print $NF}' 2>/dev/null || echo "N/A")
    print_ok "GPU: $GPU"
    print_ok "CUDA: $CUDA_VER"
    GPU_AVAILABLE=true
else
    print_warn "NVIDIA GPU 미감지 → CPU 모드로 설치됩니다"
    GPU_AVAILABLE=false
fi

# RAM 확인
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
print_ok "RAM: ${RAM_GB}GB"

# ── 2. 기존 Ollama 확인 ──────────────────────────────────────
print_step "2/5" "기존 Ollama 설치 확인"

if command -v ollama &>/dev/null; then
    EXISTING_VER=$(ollama --version 2>/dev/null || echo "unknown")
    print_warn "Ollama가 이미 설치되어 있습니다: $EXISTING_VER"
    echo -e "  재설치하시겠습니까? (최신 버전으로 업데이트) [y/N]: \c"
    read -r REPLY
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "설치를 건너뜁니다."
        SKIP_INSTALL=true
    fi
fi

# ── 3. Ollama 설치 ────────────────────────────────────────────
if [[ "$SKIP_INSTALL" != "true" ]]; then
    print_step "3/5" "Ollama 설치 중..."
    print_info "공식 설치 스크립트 실행: curl -fsSL https://ollama.com/install.sh | sh"
    echo ""

    curl -fsSL https://ollama.com/install.sh | sh

    echo ""
    print_ok "Ollama 설치 완료"
else
    print_step "3/5" "설치 단계 건너뜀"
fi

# ── 4. 서비스 시작 및 확인 ────────────────────────────────────
print_step "4/5" "Ollama 서비스 설정"

# systemd 서비스 활성화
if systemctl is-active --quiet ollama 2>/dev/null; then
    print_ok "Ollama 서비스 이미 실행 중"
else
    print_info "Ollama 서비스 시작 중..."
    sudo systemctl enable ollama 2>/dev/null || true
    sudo systemctl start ollama 2>/dev/null || ollama serve &>/dev/null &
    sleep 3
fi

# API 응답 확인
print_info "API 응답 확인 중..."
for i in {1..10}; do
    if curl -s http://localhost:11434 &>/dev/null; then
        print_ok "Ollama API 정상 응답 (http://localhost:11434)"
        break
    fi
    sleep 1
done

# 버전 출력
OLLAMA_VER=$(ollama --version 2>/dev/null || echo "확인 불가")
print_ok "설치된 버전: $OLLAMA_VER"

# ── 5. 모델 선택 및 다운로드 ─────────────────────────────────
print_step "5/5" "모델 선택 (RTX 5070 12GB VRAM 기준)"

echo ""
echo -e "  ${BOLD}#   모델            용도                       크기    VRAM${NC}"
echo -e "  ──────────────────────────────────────────────────────────────"
echo -e "  ${CYAN}1${NC}   gemma4:e2b      초경량 / 테스트용           ~1.5GB  ~2GB"
echo -e "  ${CYAN}2${NC}   gemma4:e4b      일반 대화 / 빠른 추론       ~3.5GB  ~4GB  ${GREEN}(권장)${NC}"
echo -e "  ${CYAN}3${NC}   gemma4:26b      고품질 추론 / 이미지 분석   ~14GB   VRAM+RAM"
echo -e "  ${CYAN}4${NC}   gemma4:31b      최고 성능 / 대형 작업       ~20GB   VRAM+RAM"
echo ""
echo -e "  ${YELLOW}※ 26b/31b 는 VRAM 12GB 초과 → RAM offload 사용 (속도 저하)${NC}"
echo ""
echo -e "  다운로드할 모델 번호를 입력하세요 (예: 1 2 3 / all / skip): \c"
read -r MODEL_INPUT

# 선택 파싱
declare -A MODELS_TO_PULL
if [[ "$MODEL_INPUT" == "all" ]]; then
    MODELS_TO_PULL=( ["gemma4:e2b"]=1 ["gemma4:e4b"]=1 ["gemma4:26b"]=1 ["gemma4:31b"]=1 )
elif [[ "$MODEL_INPUT" == "skip" ]] || [[ -z "$MODEL_INPUT" ]]; then
    print_warn "모델 다운로드를 건너뜁니다."
else
    for num in $MODEL_INPUT; do
        case $num in
            1) MODELS_TO_PULL["gemma4:e2b"]=1 ;;
            2) MODELS_TO_PULL["gemma4:e4b"]=1 ;;
            3) MODELS_TO_PULL["gemma4:26b"]=1 ;;
            4) MODELS_TO_PULL["gemma4:31b"]=1 ;;
            *) print_warn "알 수 없는 번호: $num (건너뜀)" ;;
        esac
    done
fi

# 선택된 모델 순서대로 다운로드
PULL_ORDER=("gemma4:e2b" "gemma4:e4b" "gemma4:26b" "gemma4:31b")
DOWNLOADED=()

for model in "${PULL_ORDER[@]}"; do
    if [[ "${MODELS_TO_PULL[$model]}" == "1" ]]; then
        echo ""
        print_info "${model} 다운로드 중... (네트워크 속도에 따라 수 분 소요)"
        if ollama pull "$model"; then
            print_ok "${model} 완료"
            DOWNLOADED+=("$model")
        else
            print_err "${model} 다운로드 실패"
        fi
    fi
done

# 테스트 실행
if [[ ${#DOWNLOADED[@]} -gt 0 ]]; then
    TEST_MODEL="${DOWNLOADED[0]}"
    echo ""
    echo -e "  ${BOLD}${TEST_MODEL} 으로 동작 테스트할까요? [y/N]:${NC} \c"
    read -r TEST_VISION
    if [[ $TEST_VISION =~ ^[Yy]$ ]]; then
        print_info "추론 테스트 중..."
        ollama run "$TEST_MODEL" "안녕하세요! RTX 5070에서 정상 동작하는지 확인해줘. 한국어로 답해줘."
    fi
fi

# ── 완료 요약 ────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║           설치 완료!                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}주요 명령어:${NC}"
echo -e "  ${CYAN}ollama run gemma4:e2b${NC}              # 초경량 모델 실행"
echo -e "  ${CYAN}ollama run gemma4:e4b${NC}              # 일반 대화"
echo -e "  ${CYAN}ollama run gemma4:26b${NC}              # 고품질 추론"
echo -e "  ${CYAN}ollama run gemma4:31b${NC}              # 최고 성능"
echo -e "  ${CYAN}ollama list${NC}                        # 설치된 모델 목록"
echo -e "  ${CYAN}ollama ps${NC}                          # 실행 중인 모델"
echo ""
echo -e "  ${BOLD}API 사용:${NC}"
echo -e "  ${CYAN}curl http://localhost:11434/api/tags${NC}   # 모델 목록 API"
echo ""
echo -e "  ${BOLD}이미지 분석:${NC}"
echo -e "  ${CYAN}ollama run gemma4:e4b \"설명해줘\" /path/to/image.png${NC}"
echo ""
echo -e "  ${BOLD}서비스 관리:${NC}"
echo -e "  ${CYAN}sudo systemctl status ollama${NC}       # 상태 확인"
echo -e "  ${CYAN}sudo systemctl restart ollama${NC}      # 재시작"
echo ""
