#!/usr/bin/env python3
"""Simple benchmark for CCG Daemon performance."""

import asyncio
import statistics
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from ccg_client import submit_task, get_task_status


async def benchmark_submit(n: int):
    """Benchmark task submission."""
    times = []

    for _ in range(n):
        start = time.perf_counter()
        task_id = submit_task({"cmd": ["echo", "test"]})
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

        if not task_id:
            print("❌ Submit failed (daemon not available)")
            return None

    return times


async def benchmark_status(n: int):
    """Benchmark status queries."""
    # Create a task first
    task_id = submit_task({"cmd": ["echo", "test"]})
    if not task_id:
        return None

    await asyncio.sleep(0.5)  # Let it complete

    times = []
    for _ in range(n):
        start = time.perf_counter()
        get_task_status(task_id)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    return times


async def benchmark_concurrent(n: int):
    """Benchmark concurrent task submissions."""
    start = time.perf_counter()

    tasks = []
    for _ in range(n):
        task_id = submit_task({"cmd": ["sleep", "0.1"]})
        if task_id:
            tasks.append(task_id)

    # Wait for all to complete
    await asyncio.sleep(2)

    elapsed = time.perf_counter() - start
    return elapsed, len(tasks)


def print_stats(name: str, times: list, target_p95: float):
    """Print statistics."""
    if not times:
        print(f"❌ {name}: No data")
        return

    p50 = statistics.median(times)
    p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile
    p99 = statistics.quantiles(times, n=100)[98]

    status = "✅" if p95 < target_p95 else "❌"
    print(f"{status} {name}:")
    print(f"   p50: {p50:.1f}ms, p95: {p95:.1f}ms, p99: {p99:.1f}ms")
    print(f"   Target p95: <{target_p95}ms")


async def main():
    """Run benchmarks."""
    print("🚀 CCG Daemon Performance Benchmark\n")

    # Benchmark submit
    print("📊 Task Submit (100 samples)...")
    submit_times = await benchmark_submit(100)
    if submit_times:
        print_stats("Submit", submit_times, 10.0)

    print()

    # Benchmark status
    print("📊 Task Status (100 samples)...")
    status_times = await benchmark_status(100)
    if status_times:
        print_stats("Status", status_times, 5.0)

    print()

    # Benchmark concurrent
    print("📊 Concurrent Tasks...")
    for n in [1, 10, 50]:
        elapsed, count = await benchmark_concurrent(n)
        print(f"   {n} tasks: {elapsed:.2f}s ({count} submitted)")


if __name__ == "__main__":
    asyncio.run(main())
