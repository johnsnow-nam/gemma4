"""API-004: 시스템 리소스 (CPU / RAM / 디스크)"""
from __future__ import annotations
import shutil
import psutil


class SystemMonitor:
    def get_status(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        disk_free_gb = round((disk.total - disk.used) / 1e9, 1)

        return {
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / 1e9, 1),
            "ram_total_gb": round(mem.total / 1e9, 1),
            "ram_percent": mem.percent,
            "disk_used_gb": round(disk.used / 1e9, 1),
            "disk_total_gb": round(disk.total / 1e9, 1),
            "disk_percent": round(disk.used / disk.total * 100, 1),
            "disk_free_gb": disk_free_gb,
            "warn_disk": disk_free_gb < 5,
            "warn_ram": mem.percent > 90,
            "warn_cpu": cpu > 90,
        }
