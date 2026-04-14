# 시스템 모니터링 대시보드 작업 지침서
> Gemma4 + Ollama + Telegram Bot + Open WebUI 통합 모니터링 GUI
> 작성일: 2026-04-14
> Claude Code에게 전달하는 구현 명세서

---

## 개발 현황 범례

| 기호 | 의미 |
|---|---|
| ✅ | 개발 완료 |
| 🔧 | 개발 중 |
| ⬜ | 미개발 |

---

## 1. 프로젝트 개요

### 1.1 목표
```
브라우저에서 http://localhost:9090 접속
→ 전체 시스템 상태를 한눈에 확인
→ 중지된 서비스는 Start 버튼으로 바로 시작
→ 5초마다 자동 새로고침
→ 로그 실시간 확인
```

### 1.2 모니터링 대상 서비스
```
1. Ollama          — AI 모델 서버 (localhost:11434)
2. gemma4:e4b      — 로드된 모델 상태
3. gemma4:26b      — 로드된 모델 상태
4. Open WebUI      — 웹 UI 서버 (localhost:8080)
5. Telegram Bot    — seokhee_gemma_bot (systemd 서비스)
6. GPU (RTX 5070)  — VRAM 사용량, 온도, 사용률
7. 시스템 리소스   — CPU, RAM, 디스크
```

### 1.3 기술 스택
```
백엔드:  Python 3.11 + FastAPI + uvicorn
프론트:  HTML + CSS + JavaScript (순수, 프레임워크 없음)
통신:    WebSocket (실시간) + REST API
프로세스: subprocess, psutil, nvidia-ml-py3
의존성:  pip install fastapi uvicorn psutil pynvml requests
실행:    python3 monitor.py
접속:    http://localhost:9090
```

### 1.4 프로젝트 구조
```
system-monitor/
├── monitor.py           # FastAPI 백엔드 메인
├── api/
│   ├── __init__.py
│   ├── services.py      # 서비스 상태 체크
│   ├── gpu.py           # GPU 모니터링
│   ├── system.py        # CPU/RAM/디스크
│   └── actions.py       # 시작/중지/재시작 액션
├── static/
│   ├── index.html       # 대시보드 메인 페이지
│   ├── style.css        # 스타일
│   └── dashboard.js     # 실시간 업데이트 로직
├── install.sh           # 자동 설치
└── monitor.service      # systemd 서비스 파일
```

---

## 2. 백엔드 API 구현

### ⬜ API-001: FastAPI 메인 서버 (monitor.py)
```python
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from api.services import ServiceMonitor
from api.gpu import GPUMonitor
from api.system import SystemMonitor
from api.actions import ServiceActions

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

service_monitor = ServiceMonitor()
gpu_monitor = GPUMonitor()
system_monitor = SystemMonitor()
actions = ServiceActions()

@app.get("/")
async def root():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

@app.get("/api/status")
async def get_status():
    """전체 시스템 상태 조회"""
    return {
        "services": service_monitor.get_all(),
        "gpu": gpu_monitor.get_status(),
        "system": system_monitor.get_status(),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/service/{name}/start")
async def start_service(name: str):
    result = actions.start(name)
    return {"success": result["success"], "message": result["message"]}

@app.post("/api/service/{name}/stop")
async def stop_service(name: str):
    result = actions.stop(name)
    return {"success": result["success"], "message": result["message"]}

@app.post("/api/service/{name}/restart")
async def restart_service(name: str):
    result = actions.restart(name)
    return {"success": result["success"], "message": result["message"]}

@app.get("/api/service/{name}/logs")
async def get_logs(name: str, lines: int = 50):
    return {"logs": actions.get_logs(name, lines)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket으로 5초마다 실시간 상태 푸시"""
    await websocket.accept()
    try:
        while True:
            data = {
                "services": service_monitor.get_all(),
                "gpu": gpu_monitor.get_status(),
                "system": system_monitor.get_status(),
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9090)
```

### ⬜ API-002: 서비스 모니터 (api/services.py)
```python
import subprocess
import requests
import psutil
from datetime import datetime

class ServiceMonitor:
    SERVICES = {
        "ollama": {
            "label": "Ollama",
            "type": "http",
            "url": "http://localhost:11434",
            "systemd": "ollama",
            "icon": "AI"
        },
        "open-webui": {
            "label": "Open WebUI",
            "type": "http",
            "url": "http://localhost:8080",
            "systemd": "open-webui",
            "icon": "WEB"
        },
        "telegram-bot": {
            "label": "Telegram Bot",
            "type": "systemd",
            "systemd": "telegram-agent",
            "icon": "BOT"
        },
    }

    def get_all(self) -> dict:
        result = {}
        for key, config in self.SERVICES.items():
            result[key] = self._check_service(key, config)

        # Ollama 모델 상태 추가
        result["models"] = self._check_ollama_models()
        return result

    def _check_service(self, key: str, config: dict) -> dict:
        status = "stopped"
        detail = ""

        # HTTP 체크
        if config["type"] == "http":
            try:
                r = requests.get(config["url"], timeout=2)
                status = "running" if r.status_code < 500 else "error"
            except:
                status = "stopped"

        # systemd 체크
        systemd_name = config.get("systemd")
        if systemd_name:
            try:
                r = subprocess.run(
                    ["systemctl", "is-active", systemd_name],
                    capture_output=True, text=True
                )
                systemd_status = r.stdout.strip()
                if systemd_status == "active":
                    if status == "stopped":
                        status = "running"
                elif systemd_status == "failed":
                    status = "error"
                else:
                    status = "stopped"
            except:
                pass

        # 업타임 계산
        uptime = self._get_uptime(systemd_name)

        return {
            "label": config["label"],
            "status": status,   # running / stopped / error
            "icon": config.get("icon", "SVC"),
            "uptime": uptime,
            "detail": detail,
            "systemd": systemd_name
        }

    def _check_ollama_models(self) -> list:
        """로드된 Ollama 모델 상태"""
        try:
            r = requests.get(
                "http://localhost:11434/api/ps", timeout=2
            )
            if r.status_code == 200:
                models = r.json().get("models", [])
                return [{
                    "name": m["name"],
                    "size": round(m.get("size", 0) / 1e9, 1),
                    "vram": round(m.get("size_vram", 0) / 1e9, 1),
                    "status": "loaded"
                } for m in models]
        except:
            pass
        return []

    def _get_uptime(self, service_name: str) -> str:
        if not service_name:
            return ""
        try:
            r = subprocess.run(
                ["systemctl", "show", service_name,
                 "--property=ActiveEnterTimestamp"],
                capture_output=True, text=True
            )
            # 업타임 파싱 및 반환
            return r.stdout.strip().replace(
                "ActiveEnterTimestamp=", ""
            )
        except:
            return ""
```

### ⬜ API-003: GPU 모니터 (api/gpu.py)
```python
try:
    import pynvml
    NVML_AVAILABLE = True
except:
    NVML_AVAILABLE = False

class GPUMonitor:
    def __init__(self):
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except:
                self.handle = None

    def get_status(self) -> dict:
        if not NVML_AVAILABLE or not self.handle:
            return self._fallback_nvidia_smi()

        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            temp = pynvml.nvmlDeviceGetTemperature(
                self.handle, pynvml.NVML_TEMPERATURE_GPU
            )
            name = pynvml.nvmlDeviceGetName(self.handle)

            return {
                "name": name,
                "vram_used_gb": round(mem.used / 1e9, 1),
                "vram_total_gb": round(mem.total / 1e9, 1),
                "vram_percent": round(mem.used / mem.total * 100, 1),
                "gpu_util": util.gpu,
                "temperature": temp,
                "status": "ok"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _fallback_nvidia_smi(self) -> dict:
        """pynvml 없을 때 nvidia-smi 파싱"""
        import subprocess
        try:
            r = subprocess.run([
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,"
                "utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True)
            parts = r.stdout.strip().split(", ")
            return {
                "name": parts[0],
                "vram_used_gb": round(int(parts[1]) / 1024, 1),
                "vram_total_gb": round(int(parts[2]) / 1024, 1),
                "vram_percent": round(
                    int(parts[1]) / int(parts[2]) * 100, 1
                ),
                "gpu_util": int(parts[3]),
                "temperature": int(parts[4]),
                "status": "ok"
            }
        except:
            return {"status": "unavailable"}
```

### ⬜ API-004: 시스템 리소스 (api/system.py)
```python
import psutil
import shutil

class SystemMonitor:
    def get_status(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")

        return {
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / 1e9, 1),
            "ram_total_gb": round(mem.total / 1e9, 1),
            "ram_percent": mem.percent,
            "disk_used_gb": round(disk.used / 1e9, 1),
            "disk_total_gb": round(disk.total / 1e9, 1),
            "disk_percent": round(disk.used / disk.total * 100, 1),
        }
```

### ⬜ API-005: 서비스 액션 (api/actions.py)
```python
import subprocess

SYSTEMD_MAP = {
    "ollama": "ollama",
    "open-webui": "open-webui",
    "telegram-bot": "telegram-agent",
}

class ServiceActions:
    def start(self, name: str) -> dict:
        service = SYSTEMD_MAP.get(name)
        if not service:
            return {"success": False, "message": f"알 수 없는 서비스: {name}"}
        try:
            r = subprocess.run(
                ["sudo", "systemctl", "start", service],
                capture_output=True, text=True
            )
            return {
                "success": r.returncode == 0,
                "message": r.stdout or r.stderr
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def stop(self, name: str) -> dict:
        service = SYSTEMD_MAP.get(name)
        r = subprocess.run(
            ["sudo", "systemctl", "stop", service],
            capture_output=True, text=True
        )
        return {"success": r.returncode == 0, "message": r.stdout}

    def restart(self, name: str) -> dict:
        service = SYSTEMD_MAP.get(name)
        r = subprocess.run(
            ["sudo", "systemctl", "restart", service],
            capture_output=True, text=True
        )
        return {"success": r.returncode == 0, "message": r.stdout}

    def get_logs(self, name: str, lines: int = 50) -> str:
        service = SYSTEMD_MAP.get(name, name)
        r = subprocess.run(
            ["journalctl", "-u", service, f"-n{lines}",
             "--no-pager", "--output=short"],
            capture_output=True, text=True
        )
        return r.stdout
```

---

## 3. 프론트엔드 구현

### ⬜ UI-001: 대시보드 메인 (static/index.html)
```
디자인 방향:
- 다크 테마 (터미널/서버 관리 느낌)
- 상태별 색상: 초록(running) / 빨강(stopped) / 노랑(error)
- 카드 그리드 레이아웃
- 실시간 숫자 업데이트 애니메이션

레이아웃 구성:
┌─────────────────────────────────────────┐
│  AI System Monitor        [●LIVE] 09:57 │
├──────────┬──────────┬────────┬──────────┤
│ Ollama   │Open WebUI│Telegram│  GPU     │
│ ● RUNNING│● RUNNING │● STOP  │RTX 5070  │
│ 업타임   │ 업타임   │[START] │10.2/12GB │
│[재시작]  │[재시작]  │        │ 85°C 72% │
├──────────┴──────────┴────────┴──────────┤
│ 로드된 모델                              │
│ gemma4:e4b ████░ 9.6GB  gemma4:26b ...  │
├───────────────┬─────────────────────────┤
│ CPU  ██░ 23%  │ RAM  ████░ 45.2/64GB    │
│ DISK ██░ 92%  │ (⚠ 디스크 여유 8GB)     │
├───────────────┴─────────────────────────┤
│ 로그 뷰어  [Ollama▼] [50줄▼] [새로고침] │
│ > 2026-04-14 17:09 llm request...       │
│ > 2026-04-14 17:09 model loaded...      │
└─────────────────────────────────────────┘
```

### ⬜ UI-002: 실시간 업데이트 (static/dashboard.js)
```javascript
// WebSocket으로 5초마다 자동 업데이트
const ws = new WebSocket("ws://localhost:9090/ws");

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateServices(data.services);
    updateGPU(data.gpu);
    updateSystem(data.system);
    updateTimestamp();
};

// 서비스 상태 카드 업데이트
function updateServices(services) {
    for (const [key, svc] of Object.entries(services)) {
        const card = document.getElementById(`svc-${key}`);
        if (!card) continue;

        const badge = card.querySelector(".status-badge");
        const startBtn = card.querySelector(".btn-start");
        const stopBtn = card.querySelector(".btn-stop");

        // 상태 색상
        badge.className = `status-badge ${svc.status}`;
        badge.textContent = svc.status.toUpperCase();

        // 버튼 토글
        if (startBtn) startBtn.hidden = svc.status === "running";
        if (stopBtn) stopBtn.hidden = svc.status !== "running";
    }
}

// 서비스 시작 버튼
async function startService(name) {
    const btn = document.querySelector(`#svc-${name} .btn-start`);
    btn.textContent = "시작 중...";
    btn.disabled = true;

    const res = await fetch(`/api/service/${name}/start`, {
        method: "POST"
    });
    const data = await res.json();

    if (!data.success) {
        alert(`시작 실패: ${data.message}`);
        btn.textContent = "Start";
        btn.disabled = false;
    }
    // 성공 시 WebSocket이 자동으로 상태 업데이트
}

// 로그 뷰어
async function loadLogs(serviceName) {
    const res = await fetch(
        `/api/service/${serviceName}/logs?lines=50`
    );
    const data = await res.json();
    document.getElementById("log-output").textContent = data.logs;
}

// GPU 게이지 업데이트
function updateGPU(gpu) {
    if (gpu.status !== "ok") return;
    document.getElementById("vram-used").textContent =
        `${gpu.vram_used_gb}GB`;
    document.getElementById("vram-bar").style.width =
        `${gpu.vram_percent}%`;
    document.getElementById("gpu-temp").textContent =
        `${gpu.temperature}°C`;
    document.getElementById("gpu-util").textContent =
        `${gpu.gpu_util}%`;

    // 온도 경고
    const tempEl = document.getElementById("gpu-temp");
    tempEl.className = gpu.temperature > 80 ? "warn" :
                       gpu.temperature > 70 ? "caution" : "ok";
}
```

### ⬜ UI-003: 서비스 카드 컴포넌트
```
각 서비스 카드에 표시:
┌──────────────────┐
│ [AI] Ollama      │
│ ● RUNNING        │
│ 업타임: 2h 34m   │
│ ──────────────── │
│ [재시작] [로그]  │
└──────────────────┘

중지 상태:
┌──────────────────┐
│ [BOT] Telegram   │
│ ● STOPPED        │
│ 마지막: 1h 전    │
│ ──────────────── │
│ [▶ START] [로그] │
└──────────────────┘
```

### ⬜ UI-004: 경고 알림
```
조건별 알림 배너:
- 디스크 90% 이상    → "⚠ 디스크 여유 공간 부족 (8GB)"
- GPU 온도 85°C 이상 → "🌡 GPU 과열 주의"
- 서비스 중단        → "❌ Telegram Bot 중지됨"
- VRAM 95% 이상      → "⚠ VRAM 포화 상태"
```

---

## 4. 설치 및 실행

### ⬜ INSTALL-001: 자동 설치 (install.sh)
```bash
#!/bin/bash
echo "=== 시스템 모니터 설치 ==="

# 의존성 설치
pip install fastapi uvicorn psutil pynvml requests python-dotenv

# sudo 없이 systemctl 제어 허용 (sudoers)
echo "$USER ALL=(ALL) NOPASSWD: /bin/systemctl start *,
      /bin/systemctl stop *,
      /bin/systemctl restart *" | \
      sudo tee /etc/sudoers.d/monitor-control

# systemd 서비스 등록
sudo tee /etc/systemd/system/system-monitor.service > /dev/null << EOF
[Unit]
Description=AI System Monitor Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/monitor.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable system-monitor
sudo systemctl start system-monitor

echo "✅ 설치 완료"
echo "브라우저에서 http://localhost:9090 접속"
```

---

## 5. 모니터링 항목 전체 목록

| 항목 | 체크 방법 | 이상 기준 | 상태 |
|---|---|---|---|
| Ollama 서버 | HTTP GET :11434 | 응답 없음 | ⬜ |
| gemma4:e4b 로드 | /api/ps | 언로드 | ⬜ |
| gemma4:26b 로드 | /api/ps | 언로드 | ⬜ |
| Open WebUI | HTTP GET :8080 | 응답 없음 | ⬜ |
| Telegram Bot | systemd is-active | stopped/failed | ⬜ |
| GPU VRAM | pynvml / nvidia-smi | >95% | ⬜ |
| GPU 온도 | pynvml / nvidia-smi | >85°C | ⬜ |
| GPU 사용률 | pynvml / nvidia-smi | >95% | ⬜ |
| CPU 사용률 | psutil | >90% | ⬜ |
| RAM 사용량 | psutil | >90% | ⬜ |
| 디스크 여유 | shutil | <5GB | ⬜ |
| 서비스 업타임 | systemctl show | - | ⬜ |
| 실시간 로그 | journalctl | - | ⬜ |

---

## 6. 개발 우선순위 (Phase)

### Phase 1 — MVP (반나절)
```
[ ] FastAPI 백엔드 기본 구조
[ ] 서비스 HTTP/systemd 상태 체크
[ ] GPU nvidia-smi 파싱
[ ] CPU/RAM/디스크 psutil
[ ] 기본 HTML 대시보드
[ ] 5초 자동 새로고침
[ ] Start/Stop/Restart 버튼
```

### Phase 2 — 완성 (1일)
```
[ ] WebSocket 실시간 업데이트
[ ] 로그 뷰어
[ ] 경고 알림 배너
[ ] 게이지/진행바 애니메이션
[ ] 다크 테마 완성
[ ] systemd 자동 등록
```

### Phase 3 — 고급 (선택)
```
[ ] 히스토리 그래프 (Chart.js)
[ ] 이메일/텔레그램 알림
[ ] 자동 복구 (서비스 중단 시 자동 재시작)
[ ] 모바일 반응형
```

---

## 7. Claude Code 실행 명령

```bash
mkdir -p ~/system-monitor
cd ~/system-monitor
claude

# Claude Code에게 입력:
"system-monitor-spec.md 파일을 읽고
 Phase 1 MVP부터 구현 시작해줘.

 모니터링 대상:
 1. Ollama (localhost:11434) — systemd: ollama
 2. Open WebUI (localhost:8080) — systemd: open-webui
 3. Telegram Bot — systemd: telegram-agent
 4. GPU: RTX 5070 (nvidia-smi 또는 pynvml)
 5. CPU/RAM/디스크 (psutil)

 핵심 요구사항:
 - 서비스 중지 시 Start 버튼 표시
 - 5초마다 자동 업데이트
 - 다크 테마 대시보드
 - http://localhost:9090 접속

 기술 스택: FastAPI + 순수 HTML/CSS/JS
 구현 완료 항목은 ⬜ → ✅ 로 업데이트해줘.
 완성 후 install.sh도 만들어줘."
```

---

## 8. 테스트 시나리오

```bash
# 설치
cd ~/system-monitor
chmod +x install.sh
./install.sh

# 브라우저 접속
xdg-open http://localhost:9090

# 테스트 1: 서비스 중지/시작
sudo systemctl stop telegram-agent
→ 대시보드에서 Telegram Bot이 STOPPED + [START] 버튼 표시
→ [START] 클릭 → 자동 재시작 확인

# 테스트 2: GPU 모니터링
ollama run gemma4:26b "안녕"
→ VRAM 사용량 증가 확인

# 테스트 3: 로그 뷰어
Telegram Bot 카드에서 [로그] 클릭
→ journalctl 실시간 로그 표시
```

---

*이 사양서는 Claude Code가 시스템 모니터링 대시보드를 구현하기 위한 명세입니다.*
*구현 완료 시 각 항목을 ⬜ → ✅ 로 업데이트하세요.*
