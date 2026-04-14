/* ── UI-002: 실시간 대시보드 업데이트 ─────────────────── */
'use strict';

const WS_URL = `ws://${location.host}/ws`;
let ws = null;
let reconnectTimer = null;

// ── WebSocket 연결 ──────────────────────────────────────
function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('[WS] 연결됨');
    document.getElementById('live-text').textContent = '● LIVE';
    document.getElementById('live-text').style.color = '#3fb950';
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateServices(data.services);
    updateGPU(data.gpu);
    updateSystem(data.system);
    updateTimestamp(data.timestamp);
    updateAlerts(data);
  };

  ws.onclose = () => {
    document.getElementById('live-text').textContent = '○ 연결 끊김';
    document.getElementById('live-text').style.color = '#f85149';
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => ws.close();
}

// ── 서비스 카드 업데이트 ────────────────────────────────
function updateServices(services) {
  for (const [key, svc] of Object.entries(services)) {
    if (key === 'models') {
      updateModels(svc);
      continue;
    }
    const card = document.getElementById(`svc-${key}`);
    if (!card) continue;

    // 상태 뱃지
    const badge = card.querySelector('.status-badge');
    const labels = { running: '● RUNNING', stopped: '● STOPPED', error: '⚠ ERROR' };
    badge.textContent = labels[svc.status] || svc.status.toUpperCase();
    badge.className = `status-badge ${svc.status}`;

    // 업타임
    const uptime = card.querySelector('.svc-uptime');
    if (uptime) uptime.textContent = svc.uptime ? `시작: ${svc.uptime}` : '';

    // 버튼 토글
    const btnStart   = card.querySelector('.btn-start');
    const btnStop    = card.querySelector('.btn-stop');
    const btnRestart = card.querySelector('.btn-restart');
    const running = svc.status === 'running';
    if (btnStart)   btnStart.hidden   = running;
    if (btnStop)    btnStop.hidden    = !running;
    if (btnRestart) btnRestart.hidden = !running;
  }
}

// ── 로드된 모델 목록 ────────────────────────────────────
function updateModels(models) {
  const container = document.getElementById('model-list');
  if (!container) return;
  if (!models || models.length === 0) {
    container.innerHTML = '<span class="model-empty">로드된 모델 없음</span>';
    return;
  }
  container.innerHTML = models.map(m => `
    <div class="model-item">
      <span class="model-badge">LOADED</span>
      <span class="model-name">${m.name}</span>
      <span class="model-vram">${m.vram_gb}GB VRAM / ${m.size_gb}GB</span>
    </div>
  `).join('');
}

// ── GPU 상태 업데이트 ───────────────────────────────────
function updateGPU(gpu) {
  if (!gpu || gpu.status === 'unavailable') {
    document.getElementById('gpu-name').textContent = 'GPU 정보 없음';
    return;
  }
  if (gpu.status === 'error') return;

  setText('gpu-name', gpu.name || 'GPU');

  const vramPct = gpu.vram_percent;
  const tempVal = gpu.temperature;
  const utilVal = gpu.gpu_util;

  // VRAM
  setGauge('vram', `${gpu.vram_used_gb} / ${gpu.vram_total_gb} GB`, vramPct,
    vramPct > 95 ? 'danger' : vramPct > 80 ? 'warn' : '');

  // 온도
  const tempEl = document.getElementById('gpu-temp-val');
  if (tempEl) {
    tempEl.textContent = `${tempVal}°C`;
    tempEl.className = 'stat-value' + (tempVal > 85 ? ' danger' : tempVal > 75 ? ' warn' : '');
  }

  // GPU 사용률
  const utilEl = document.getElementById('gpu-util-val');
  if (utilEl) {
    utilEl.textContent = `${utilVal}%`;
    utilEl.className = 'stat-value' + (utilVal > 95 ? ' danger' : '');
  }
}

// ── 시스템 리소스 업데이트 ─────────────────────────────
function updateSystem(sys) {
  if (!sys) return;

  // CPU
  const cpuEl = document.getElementById('cpu-val');
  if (cpuEl) {
    cpuEl.textContent = `${sys.cpu_percent}%`;
    cpuEl.className = 'resource-value' + (sys.warn_cpu ? ' danger' : '');
  }
  setGauge('cpu', `${sys.cpu_percent}%`, sys.cpu_percent,
    sys.cpu_percent > 90 ? 'danger' : sys.cpu_percent > 70 ? 'warn' : '');

  // RAM
  const ramEl = document.getElementById('ram-val');
  if (ramEl) {
    ramEl.textContent = `${sys.ram_percent}%`;
    ramEl.className = 'resource-value' + (sys.warn_ram ? ' danger' : '');
  }
  setGauge('ram', `${sys.ram_used_gb} / ${sys.ram_total_gb} GB`, sys.ram_percent,
    sys.ram_percent > 90 ? 'danger' : sys.ram_percent > 75 ? 'warn' : '');

  // 디스크
  const diskEl = document.getElementById('disk-val');
  if (diskEl) {
    diskEl.textContent = `${sys.disk_percent}%`;
    diskEl.className = 'resource-value' + (sys.warn_disk ? ' danger' : '');
  }
  setGauge('disk', `${sys.disk_used_gb} / ${sys.disk_total_gb} GB (여유 ${sys.disk_free_gb}GB)`,
    sys.disk_percent,
    sys.warn_disk ? 'danger' : sys.disk_percent > 80 ? 'warn' : '');
}

// ── 경고 배너 업데이트 ──────────────────────────────────
function updateAlerts(data) {
  const banner = document.getElementById('alert-banner');
  const alerts = [];

  // GPU 경고
  if (data.gpu && data.gpu.status === 'ok') {
    if (data.gpu.temperature > 85)
      alerts.push({ text: `🌡 GPU 과열 주의 (${data.gpu.temperature}°C)`, danger: true });
    if (data.gpu.vram_percent > 95)
      alerts.push({ text: `⚠ VRAM 포화 상태 (${data.gpu.vram_percent}%)`, danger: true });
  }

  // 시스템 경고
  if (data.system) {
    if (data.system.warn_disk)
      alerts.push({ text: `⚠ 디스크 여유 공간 부족 (${data.system.disk_free_gb}GB 남음)`, danger: false });
    if (data.system.warn_ram)
      alerts.push({ text: `⚠ RAM 사용량 높음 (${data.system.ram_percent}%)`, danger: false });
  }

  // 서비스 중단 경고
  if (data.services) {
    for (const [key, svc] of Object.entries(data.services)) {
      if (key === 'models') continue;
      if (svc.status === 'stopped')
        alerts.push({ text: `❌ ${svc.label} 서비스 중지됨`, danger: true });
      if (svc.status === 'error')
        alerts.push({ text: `⚠ ${svc.label} 오류 상태`, danger: false });
    }
  }

  banner.innerHTML = alerts.map(a =>
    `<div class="alert-item${a.danger ? ' danger' : ''}">${a.text}</div>`
  ).join('');
}

// ── 타임스탬프 ──────────────────────────────────────────
function updateTimestamp(ts) {
  const el = document.getElementById('timestamp');
  if (!el) return;
  const d = ts ? new Date(ts) : new Date();
  el.textContent = d.toLocaleTimeString('ko-KR');
}

// ── 서비스 액션 ─────────────────────────────────────────
window.serviceAction = async function(name, action) {
  const card = document.getElementById(`svc-${name}`);
  const btn = card?.querySelector(`.btn-${action}`);
  if (btn) { btn.disabled = true; btn.textContent = '처리 중...'; }

  try {
    const res = await fetch(`/api/service/${name}/${action}`, { method: 'POST' });
    const data = await res.json();
    if (!data.success) alert(`실패: ${data.message}`);
  } catch (e) {
    alert(`요청 실패: ${e.message}`);
  } finally {
    if (btn) { btn.disabled = false; }
  }
};

// ── 로그 뷰어 ───────────────────────────────────────────
window.loadLogs = async function() {
  const name = document.getElementById('log-service').value;
  const lines = document.getElementById('log-lines').value;
  const output = document.getElementById('log-output');
  output.textContent = '로그 불러오는 중...';
  try {
    const res = await fetch(`/api/service/${name}/logs?lines=${lines}`);
    const data = await res.json();
    output.textContent = data.logs || '(로그 없음)';
    output.scrollTop = output.scrollHeight;
  } catch (e) {
    output.textContent = `로그 조회 실패: ${e.message}`;
  }
};

// ── 유틸 ────────────────────────────────────────────────
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setGauge(prefix, labelText, pct, cls) {
  const label = document.getElementById(`${prefix}-label`);
  const fill  = document.getElementById(`${prefix}-fill`);
  if (label) label.textContent = labelText;
  if (fill) {
    fill.style.width = `${Math.min(pct, 100)}%`;
    fill.className = `progress-fill${cls ? ' ' + cls : ''}`;
  }
}

// ── 초기화 ──────────────────────────────────────────────
connect();
