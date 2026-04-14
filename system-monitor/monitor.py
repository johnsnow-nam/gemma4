#!/usr/bin/env python3
"""API-001: AI System Monitor — FastAPI + WebSocket 백엔드"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.services import ServiceMonitor
from api.gpu import GPUMonitor
from api.system import SystemMonitor
from api.actions import ServiceActions

app = FastAPI(title="AI System Monitor")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

service_monitor = ServiceMonitor()
gpu_monitor = GPUMonitor()
system_monitor = SystemMonitor()
actions = ServiceActions()


# ─── 페이지 ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ─── REST API ─────────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    return {
        "services": service_monitor.get_all(),
        "gpu": gpu_monitor.get_status(),
        "system": system_monitor.get_status(),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/service/{name}/start")
async def start_service(name: str):
    result = actions.start(name)
    return result


@app.post("/api/service/{name}/stop")
async def stop_service(name: str):
    result = actions.stop(name)
    return result


@app.post("/api/service/{name}/restart")
async def restart_service(name: str):
    result = actions.restart(name)
    return result


@app.get("/api/service/{name}/logs")
async def get_logs(name: str, lines: int = 50):
    return {"logs": actions.get_logs(name, lines)}


# ─── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "services": service_monitor.get_all(),
                "gpu": gpu_monitor.get_status(),
                "system": system_monitor.get_status(),
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_text(json.dumps(data, ensure_ascii=False))
            await asyncio.sleep(5)
    except (WebSocketDisconnect, Exception):
        pass


# ─── 진입점 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("🖥  AI System Monitor 시작 → http://localhost:9090")
    uvicorn.run(app, host="127.0.0.1", port=9090, log_level="warning")
