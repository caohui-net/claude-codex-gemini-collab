#!/usr/bin/env python3
"""错误恢复策略"""
from typing import Optional, Callable, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


class RecoveryStrategy:
    """错误恢复策略"""

    @staticmethod
    def fallback(primary_func: Callable, fallback_func: Callable, *args, **kwargs) -> Any:
        """主函数失败时回退到备用函数"""
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            print(f"⚠️  Primary failed: {e}, trying fallback", file=sys.stderr)
            return fallback_func(*args, **kwargs)

    @staticmethod
    def degrade(func: Callable, default_value: Any, *args, **kwargs) -> Any:
        """函数失败时返回降级默认值"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"⚠️  Function failed: {e}, using default", file=sys.stderr)
            return default_value

    @staticmethod
    def circuit_breaker(func: Callable, max_failures: int = 3) -> Callable:
        """断路器：连续失败达到阈值后熔断"""
        failure_count = 0

        def wrapper(*args, **kwargs):
            nonlocal failure_count
            if failure_count >= max_failures:
                raise RuntimeError(f"Circuit breaker open: {failure_count} failures")

            try:
                result = func(*args, **kwargs)
                failure_count = 0  # 成功则重置
                return result
            except Exception as e:
                failure_count += 1
                raise e

        return wrapper
