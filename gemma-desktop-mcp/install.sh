#!/usr/bin/env bash
# SETUP-002: gemma-desktop-mcp 자동 설치 스크립트
# 사용법: chmod +x install.sh && ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PATH="$SCRIPT_DIR/gemma-mcp-server.py"
CONFIG_DIR="$HOME/.config/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  gemma-desktop-mcp 설치 스크립트${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ────────────────────────────────────────
# 1. Python 버전 확인
# ────────────────────────────────────────
echo -e "${YELLOW}[1/5] Python 버전 확인...${NC}"
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo -e "${RED}✖ Python3를 찾을 수 없습니다. Python 3.11+ 설치 후 재시도하세요.${NC}"
    exit 1
fi
PYVER=$($PYTHON --version 2>&1)
echo -e "${GREEN}✔ $PYVER${NC}"

# ────────────────────────────────────────
# 2. 의존성 설치
# ────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/5] Python 패키지 설치...${NC}"
$PYTHON -m pip install fastmcp ollama --quiet --upgrade
echo -e "${GREEN}✔ fastmcp, ollama 설치 완료${NC}"

# ────────────────────────────────────────
# 3. Ollama 연결 확인
# ────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/5] Ollama 연결 확인...${NC}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✔ Ollama 연결 성공 ($OLLAMA_URL)${NC}"
    # 모델 목록
    MODELS=$(curl -sf "$OLLAMA_URL/api/tags" | $PYTHON -c "
import json, sys
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print(', '.join(models) if models else '모델 없음')
" 2>/dev/null || echo "?")
    echo -e "  설치된 모델: ${CYAN}$MODELS${NC}"
else
    echo -e "${YELLOW}⚠ Ollama에 연결할 수 없습니다. 'ollama serve'를 먼저 실행하세요.${NC}"
    echo -e "  ${YELLOW}설치 후 Claude Desktop에서 사용 시 Ollama가 실행 중이어야 합니다.${NC}"
fi

# ────────────────────────────────────────
# 4. Claude Desktop 설정 파일 업데이트 (SETUP-001)
# ────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/5] Claude Desktop 설정 업데이트...${NC}"

DEFAULT_MODEL="${DEFAULT_MODEL:-gemma4:26b}"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    # 기존 설정 백업
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
    echo -e "  기존 설정 백업: $CONFIG_FILE.bak"

    # Python으로 JSON 병합 (mcpServers 항목만 추가/업데이트)
    $PYTHON << PYEOF
import json, os

config_path = "$CONFIG_FILE"
server_path = "$SERVER_PATH"
ollama_url = "$OLLAMA_URL"
default_model = "$DEFAULT_MODEL"

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

if "mcpServers" not in config:
    config["mcpServers"] = {}

config["mcpServers"]["gemma4-local"] = {
    "command": "python3",
    "args": [server_path],
    "env": {
        "OLLAMA_URL": ollama_url,
        "DEFAULT_MODEL": default_model,
    }
}

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("설정 업데이트 완료")
PYEOF
else
    # 새로 생성
    cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "gemma4-local": {
      "command": "python3",
      "args": ["$SERVER_PATH"],
      "env": {
        "OLLAMA_URL": "$OLLAMA_URL",
        "DEFAULT_MODEL": "$DEFAULT_MODEL"
      }
    }
  }
}
EOF
    echo -e "  새 설정 파일 생성"
fi

echo -e "${GREEN}✔ 설정 파일: $CONFIG_FILE${NC}"

# 설정 내용 표시
echo ""
echo -e "  ${CYAN}등록된 MCP 서버:${NC}"
echo -e "    서버명: gemma4-local"
echo -e "    실행: python3 $SERVER_PATH"
echo -e "    모델: $DEFAULT_MODEL"

# ────────────────────────────────────────
# 5. 연결 테스트
# ────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] MCP 서버 문법 검사...${NC}"
$PYTHON -c "
import sys, ast
sys.path.insert(0, '$SCRIPT_DIR')
files = [
    '$SERVER_PATH',
    '$SCRIPT_DIR/tools/ollama_tool.py',
    '$SCRIPT_DIR/tools/file_tool.py',
    '$SCRIPT_DIR/tools/folder_tool.py',
    '$SCRIPT_DIR/tools/image_tool.py',
    '$SCRIPT_DIR/tools/shell_tool.py',
    '$SCRIPT_DIR/tools/git_tool.py',
    '$SCRIPT_DIR/tools/project_tool.py',
    '$SCRIPT_DIR/config/settings.py',
]
ok = True
for f in files:
    try:
        with open(f) as fp:
            ast.parse(fp.read())
    except SyntaxError as e:
        print(f'  ✖ {f}: {e}')
        ok = False
if ok:
    print('  모든 파일 문법 OK')
"
echo -e "${GREEN}✔ 문법 검사 완료${NC}"

# ────────────────────────────────────────
# 완료 안내
# ────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  설치 완료!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "다음 단계:"
echo -e "  1. ${YELLOW}Claude Desktop을 완전히 종료${NC}하세요."
echo -e "  2. ${YELLOW}Claude Desktop을 다시 실행${NC}하세요."
echo -e "  3. 채팅창 하단에 ${CYAN}🔧 MCP 아이콘${NC}이 나타나면 성공입니다."
echo -e "  4. 아이콘 클릭 → ${CYAN}gemma4-local${NC} 도구 목록 확인"
echo ""
echo -e "사용 예시:"
echo -e "  \"${CYAN}ask_gemma 도구로 OCPP BootNotification 설명해줘${NC}\""
echo -e "  \"${CYAN}read_file로 ~/main.c 읽어서 분석해줘${NC}\""
echo -e "  \"${CYAN}get_system_info로 현재 GPU 상태 알려줘${NC}\""
echo ""
echo -e "문제 발생 시: ${YELLOW}$CONFIG_FILE${NC} 확인"
echo -e "로그: Claude Desktop → 설정 → Developer → MCP Logs"
