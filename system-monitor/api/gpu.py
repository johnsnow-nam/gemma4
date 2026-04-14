"""API-003: GPU 모니터링 (pynvml / nvidia-smi 폴백)"""
from __future__ import annotations
import subprocess

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUMonitor:
    def __init__(self):
        self.handle = None
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                self.handle = None

    def get_status(self) -> dict:
        if NVML_AVAILABLE and self.handle:
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                temp = pynvml.nvmlDeviceGetTemperature(
                    self.handle, pynvml.NVML_TEMPERATURE_GPU
                )
                name = pynvml.nvmlDeviceGetName(self.handle)
                if isinstance(name, bytes):
                    name = name.decode()
                return {
                    "name": name,
                    "vram_used_gb": round(mem.used / 1e9, 1),
                    "vram_total_gb": round(mem.total / 1e9, 1),
                    "vram_percent": round(mem.used / mem.total * 100, 1),
                    "gpu_util": util.gpu,
                    "temperature": temp,
                    "status": "ok",
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return self._fallback_nvidia_smi()

    def _fallback_nvidia_smi(self) -> dict:
        try:
            r = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            used_mb = int(parts[1])
            total_mb = int(parts[2])
            return {
                "name": parts[0],
                "vram_used_gb": round(used_mb / 1024, 1),
                "vram_total_gb": round(total_mb / 1024, 1),
                "vram_percent": round(used_mb / total_mb * 100, 1),
                "gpu_util": int(parts[3]),
                "temperature": int(parts[4]),
                "status": "ok",
            }
        except Exception:
            return {"status": "unavailable"}
