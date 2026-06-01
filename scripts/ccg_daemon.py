#!/usr/bin/env python3
"""CCG Collaboration Daemon - MVP implementation."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Deque

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn


# Global state
tasks: Dict[str, dict] = {}
task_events: Dict[str, Deque[dict]] = {}  # Ring buffer of events per task
daemon_root: Optional[Path] = None
daemon_token: Optional[str] = None
daemon_server = None
audit_log_path: Optional[Path] = None
MAX_EVENTS_PER_TASK = 100


def write_audit_log(entry: dict):
    """Write audit log entry."""
    if not audit_log_path:
        return

    try:
        with open(audit_log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        print(f"⚠️  Audit log write failed: {e}", file=sys.stderr)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup: schedule runtime file write as background task
    if daemon_server and daemon_token:
        asyncio.create_task(write_runtime_after_start(daemon_server, daemon_token))
    yield
    # Shutdown: cleanup runtime file
    cleanup_runtime_file()


app = FastAPI(title="CCG Daemon", version="0.1.0", lifespan=lifespan)


def get_runtime_file() -> Path:
    """Get runtime discovery file path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "ccg-daemon.json"
    return Path.home() / ".cache" / "ccg-daemon.json"


def write_runtime_file(port: int, token: str):
    """Write daemon runtime info to discovery file."""
    runtime_file = get_runtime_file()
    runtime_file.parent.mkdir(parents=True, exist_ok=True)

    runtime_info = {
        "pid": os.getpid(),
        "port": port,
        "token": token,
        "root": str(daemon_root),
        "started_at": datetime.now(timezone.utc).isoformat()
    }

    runtime_file.write_text(json.dumps(runtime_info, indent=2))


def cleanup_runtime_file():
    """Remove runtime file on shutdown."""
    runtime_file = get_runtime_file()
    if runtime_file.exists():
        runtime_file.unlink()


def emit_event(task_id: str, event_type: str, payload: dict):
    """Emit an event for a task."""
    if task_id not in task_events:
        task_events[task_id] = deque(maxlen=MAX_EVENTS_PER_TASK)

    event = {
        "event_id": str(uuid.uuid4()),
        "task_id": task_id,
        "type": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        "seq": len(task_events[task_id]),
        "payload": payload
    }

    task_events[task_id].append(event)


def validate_path(path: str) -> bool:
    """Validate path is within workspace root."""
    try:
        resolved = Path(path).resolve(strict=False)
        resolved.relative_to(daemon_root)
        return True
    except (ValueError, RuntimeError):
        return False


async def execute_task(task_id: str):
    """Execute a task in subprocess."""
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    emit_event(task_id, "task_started", {"task_id": task_id})

    task_data = task.get("data", {})
    timeout = task_data.get("timeout", 300)  # Default 5 min

    try:
        # Validate paths if present
        if "cwd" in task_data:
            if not validate_path(task_data["cwd"]):
                raise ValueError(f"Invalid path: {task_data['cwd']}")

        # Execute subprocess with process group isolation
        proc = await asyncio.create_subprocess_exec(
            *task_data.get("cmd", ["echo", "no command"]),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=task_data.get("cwd", str(daemon_root)),
            start_new_session=True  # Process group isolation
        )

        # Send stdin data
        # If task_data has "stdin" field, use it; otherwise send task_data as JSON
        if "stdin" in task_data:
            stdin_data = task_data["stdin"].encode() if isinstance(task_data["stdin"], str) else task_data["stdin"]
        else:
            stdin_data = json.dumps(task_data).encode()

        # Wait with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data),
                timeout=timeout
            )

            task["status"] = "completed"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["exit_code"] = proc.returncode
            task["stdout"] = stdout.decode()
            task["stderr"] = stderr.decode()

            emit_event(task_id, "task_completed", {
                "task_id": task_id,
                "exit_code": proc.returncode
            })

            # Audit log
            write_audit_log({
                "task_id": task_id,
                "timestamp": task["completed_at"],
                "cmd": task_data.get("cmd", []),
                "cwd": task_data.get("cwd", str(daemon_root)),
                "status": "completed",
                "exit_code": proc.returncode,
                "duration_sec": (datetime.fromisoformat(task["completed_at"]) -
                                datetime.fromisoformat(task["started_at"])).total_seconds()
            })

        except asyncio.TimeoutError:
            # Timeout: SIGTERM → grace period → SIGKILL
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                await proc.wait()

            task["status"] = "timeout"
            task["timeout_at"] = datetime.now(timezone.utc).isoformat()
            emit_event(task_id, "task_timeout", {"task_id": task_id})

            # Audit log
            write_audit_log({
                "task_id": task_id,
                "timestamp": task["timeout_at"],
                "cmd": task_data.get("cmd", []),
                "cwd": task_data.get("cwd", str(daemon_root)),
                "status": "timeout",
                "exit_code": -1,
                "duration_sec": timeout
            })

    except Exception as e:
        task["status"] = "failed"
        task["failed_at"] = datetime.now(timezone.utc).isoformat()
        task["error"] = str(e)
        emit_event(task_id, "task_failed", {"task_id": task_id, "error": str(e)})

        # Audit log
        write_audit_log({
            "task_id": task_id,
            "timestamp": task["failed_at"],
            "cmd": task_data.get("cmd", []),
            "cwd": task_data.get("cwd", str(daemon_root)),
            "status": "failed",
            "error": str(e),
            "exit_code": -1
        })


def cleanup_old_tasks():
    """Clean up old completed/failed/timeout tasks."""
    now = datetime.now(timezone.utc)
    to_delete = []

    for task_id, task in tasks.items():
        status = task.get("status")

        # Never clean running/pending tasks
        if status in ("running", "pending"):
            continue

        # Check TTL (30 minutes)
        completed_at = task.get("completed_at") or task.get("failed_at") or task.get("timeout_at")
        if completed_at:
            completed_time = datetime.fromisoformat(completed_at)
            age_minutes = (now - completed_time).total_seconds() / 60
            if age_minutes > 30:
                to_delete.append(task_id)

    # Also enforce max count (keep most recent 1000)
    finished_tasks = [(tid, t) for tid, t in tasks.items()
                      if t.get("status") not in ("running", "pending")]
    if len(finished_tasks) > 1000:
        # Sort by completion time, delete oldest
        finished_tasks.sort(key=lambda x: x[1].get("completed_at", ""))
        for task_id, _ in finished_tasks[:-1000]:
            to_delete.append(task_id)

    # Delete tasks and their events
    for task_id in set(to_delete):
        tasks.pop(task_id, None)
        task_events.pop(task_id, None)

    return len(to_delete)


@app.post("/tasks/submit")
async def submit_task(task_data: dict):
    """Submit a new task."""
    # Cleanup old tasks on submit
    cleanup_old_tasks()

    task_id = str(uuid.uuid4())

    task = {
        "id": task_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": task_data
    }

    tasks[task_id] = task
    emit_event(task_id, "task_created", {"task_id": task_id})

    # Start task execution in background
    asyncio.create_task(execute_task(task_id))

    return {"task_id": task_id, "status": "pending"}


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task["status"] in ("completed", "failed", "cancelled"):
        return {"message": "Task already finished"}

    task["status"] = "cancelled"
    task["cancelled_at"] = datetime.now(timezone.utc).isoformat()

    return {"message": "Task cancelled"}


@app.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str):
    """Stream task events via SSE."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        # Send existing events
        if task_id in task_events:
            for event in task_events[task_id]:
                yield {
                    "event": event["type"],
                    "data": json.dumps(event)
                }

        # Keep connection open for new events
        # (In MVP, just close after sending existing events)
        # TODO: Implement real-time event push in Phase 3A-3

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "tasks": len(tasks)}


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\n🛑 Received signal {signum}, shutting down...")
    cleanup_runtime_file()
    sys.exit(0)


async def write_runtime_after_start(server, token):
    """Write runtime file after server starts with actual port."""
    await asyncio.sleep(0.1)  # Wait for server to bind
    actual_port = server.servers[0].sockets[0].getsockname()[1]
    write_runtime_file(actual_port, token)
    print(f"✓ Runtime file written: {get_runtime_file()}")
    print(f"✓ Daemon ready on http://127.0.0.1:{actual_port}")


def main():
    """Start the daemon."""
    global daemon_root, daemon_token, daemon_server, audit_log_path

    # Set daemon root to current directory
    daemon_root = Path.cwd()

    # Initialize audit log path
    audit_log_path = daemon_root / ".omc" / "daemon-audit.log"
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    # Scan for incomplete tasks on startup
    print("🔍 Scanning for incomplete tasks...")
    try:
        scan_result = subprocess.run(
            [sys.executable, "scripts/collab_discuss.py", "scan"],
            cwd=daemon_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        if scan_result.returncode == 0 and scan_result.stdout:
            print(scan_result.stdout.strip())
            # Log scan to audit
            write_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "daemon_startup_scan",
                "status": "completed"
            })
    except Exception as e:
        print(f"⚠️  Startup scan failed: {e}")
        write_audit_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "daemon_startup_scan",
            "status": "failed",
            "error": str(e)
        })

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Generate auth token
    daemon_token = str(uuid.uuid4())

    # Use dynamic port (0 = let OS choose)
    port = int(os.environ.get("CCG_DAEMON_PORT", "0"))

    print(f"🚀 Starting CCG Daemon...")
    print(f"   Root: {daemon_root}")
    print(f"   Port: {port if port != 0 else 'dynamic'}")
    print(f"   Runtime file: {get_runtime_file()}")

    # Start server
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
    daemon_server = uvicorn.Server(config)

    try:
        daemon_server.run()
    finally:
        cleanup_runtime_file()


if __name__ == "__main__":
    main()
