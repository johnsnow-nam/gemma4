# =============================================================
#  Gemma AI 설치 스크립트 (Windows)
#  사용법: powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/johnsnow-nam/gemma4/master/install.ps1 | iex"
# =============================================================

$ErrorActionPreference = "Stop"
$REPO_URL   = "https://github.com/johnsnow-nam/gemma4.git"
$INSTALL_DIR = "$env:USERPROFILE\gemma4"
$MODEL      = "gemma4:e4b"

function Write-Info    { param($msg) Write-Host "[Gemma AI] $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "[완료] $msg"     -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[주의] $msg"     -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "[오류] $msg"     -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       🤖  Gemma AI 설치 시작         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ollama 확인 ────────────────────────────────────────────
Write-Info "Ollama 확인 중..."
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Err "Ollama가 설치되지 않았습니다.`nhttps://ollama.com/download 에서 먼저 설치해 주세요."
}
Write-Success "Ollama 확인됨"

# ── 2. Python 확인 ───────────────────────────────────────────
Write-Info "Python 확인 중..."
$python = $null
foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd -c "import sys; print(sys.version_info[:2])" 2>$null
        $ok  = & $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $cmd; break }
    } catch {}
}
if (-not $python) {
    Write-Err "Python 3.9 이상이 필요합니다.`nhttps://www.python.org/downloads/ 에서 설치해 주세요."
}
Write-Success "Python 확인됨 ($python)"

# ── 3. Git 확인 ──────────────────────────────────────────────
Write-Info "Git 확인 중..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git이 설치되지 않았습니다.`nhttps://git-scm.com/downloads 에서 설치해 주세요."
}
Write-Success "Git 확인됨"

# ── 4. 소스코드 다운로드 ─────────────────────────────────────
Write-Info "Gemma AI 소스코드 다운로드 중..."
if (Test-Path "$INSTALL_DIR\.git") {
    Write-Warn "이미 설치되어 있습니다. 최신 버전으로 업데이트합니다."
    git -C $INSTALL_DIR pull --quiet
} else {
    git clone --quiet $REPO_URL $INSTALL_DIR
}
Write-Success "소스코드 준비 완료 → $INSTALL_DIR"

# ── 5. Python 가상환경 + Open WebUI 설치 ─────────────────────
Write-Info "Open WebUI 설치 중... (1~3분 소요)"
Set-Location $INSTALL_DIR
& $python -m venv .venv-webui
& "$INSTALL_DIR\.venv-webui\Scripts\pip" install --quiet --upgrade pip
& "$INSTALL_DIR\.venv-webui\Scripts\pip" install --quiet open-webui
Write-Success "Open WebUI 설치 완료"

# ── 6. AI 모델 다운로드 ──────────────────────────────────────
Write-Info "AI 모델 다운로드 중: $MODEL (5~10분 소요, 처음 한 번만)"
$modelList = & ollama list 2>$null
if ($modelList -match ($MODEL -split ":")[0]) {
    Write-Success "모델이 이미 있습니다: $MODEL"
} else {
    & ollama pull $MODEL
}
Write-Success "모델 준비 완료"

# ── 7. 실행 배치 파일 생성 ───────────────────────────────────
Write-Info "실행 파일 생성 중..."
$startBat = @"
@echo off
echo 🤖 Gemma AI 시작 중...

REM Ollama 실행 (이미 실행 중이면 무시)
tasklist /FI "IMAGENAME eq ollama.exe" | find "ollama.exe" >nul 2>&1
if errorlevel 1 (
    start /B "" ollama serve
    timeout /t 2 /nobreak >nul
)

REM 브라우저 3초 후 열기
start "" /B cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8080"

REM Open WebUI 실행
set OLLAMA_API_BASE_URL=http://localhost:11434
"$INSTALL_DIR\.venv-webui\Scripts\open-webui" serve --port 8080
"@
$startBat | Out-File -FilePath "$INSTALL_DIR\start.bat" -Encoding utf8
Write-Success "실행 파일 생성됨: $INSTALL_DIR\start.bat"

# ── 8. 바탕화면 바로가기 ─────────────────────────────────────
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\Gemma AI.lnk"

$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath       = "$INSTALL_DIR\start.bat"
$sc.WorkingDirectory = $INSTALL_DIR
$sc.Description      = "Gemma AI 로컬 AI 채팅"
$sc.Save()
Write-Success "바탕화면 바로가기 생성됨"

# ── 완료 ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║     🎉  설치 완료!                   ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  바탕화면 'Gemma AI' 아이콘을        ║" -ForegroundColor Green
Write-Host "║  더블클릭하면 바로 시작됩니다!       ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
