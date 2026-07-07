#!/usr/bin/env python3
"""审计日志模块"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, log_path: str = ".collab/audit.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, agent: str, prompt: str, result: str,
            duration: float, error: Optional[str] = None):
        """记录agent调用"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "prompt": prompt[:200],  # 截断长prompt
            "result": result[:500] if result else None,  # 截断长结果
            "duration": round(duration, 2),
            "error": error,
            "success": error is None
        }

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
