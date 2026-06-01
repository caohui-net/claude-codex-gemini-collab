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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Deque

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn


app = FastAPI(title="CCG Daemon", version="0.1.0")

# Global state
tasks: Dict[str, dict] = {}
task_events: Dict[str, Deque[dict]] = {}  # Ring buffer of events per task
daemon_root: Optional[Path] = None
MAX_EVENTS_PER_TASK = 100


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


async def execute_task(task_id: str):
    """Execute a task in subprocess."""
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    emit_event(task_id, "task_started", {"task_id": task_id})

    try:
        # Simulate task execution (replace with actual subprocess)
        await asyncio.sleep(1)

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        emit_event(task_id, "task_completed", {"task_id": task_id})

    except Exception as e:
        task["status"] = "failed"
        task["failed_at"] = datetime.now(timezone.utc).isoformat()
        task["error"] = str(e)
        emit_event(task_id, "task_failed", {"task_id": task_id, "error": str(e)})


@app.post("/tasks/submit")
async def submit_task(task_data: dict):
    """Submit a new task."""
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
    global daemon_root

    # Set daemon root to current directory
    daemon_root = Path.cwd()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Generate auth token
    token = str(uuid.uuid4())

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
    server = uvicorn.Server(config)

    # Write runtime file after server starts
    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(write_runtime_after_start(server, token))

    try:
        server.run()
    finally:
        cleanup_runtime_file()


if __name__ == "__main__":
    main()
