# Coordination Backend Configuration

The coordination abstraction layer supports multiple backends for multi-agent coordination.

## Backends

### Filesystem (Default)
- **Type**: `filesystem`
- **Features**: Atomic locks via mkdir, polling-based signals/actions
- **Use case**: Single machine, local development
- **Requirements**: None (built-in)

### agentmemory
- **Type**: `agentmemory`
- **Features**: Distributed leases, real-time signals, priority-based actions via iii-engine
- **Use case**: Cross-platform, distributed multi-agent systems
- **Requirements**: 
  - agentmemory server running (port 3111 REST, port 49134 WebSocket)
  - iii-sdk Python package installed

## Configuration

Edit `.claude/settings.json`:

```json
{
  "ccgCollab": {
    "coordinationBackend": "agentmemory",
    "agentmemory": {
      "enabled": true,
      "wsUrl": "ws://localhost:49134",
      "fallbackToFilesystem": true
    }
  }
}
```

### Options

- `coordinationBackend`: `"filesystem"` or `"agentmemory"` (default: `"filesystem"`)
- `agentmemory.enabled`: Enable agentmemory backend (default: `false`)
- `agentmemory.wsUrl`: WebSocket URL for iii-engine (default: `"ws://localhost:49134"`)
- `agentmemory.fallbackToFilesystem`: Fall back to filesystem if agentmemory unavailable (default: `true`)

## Setup agentmemory

1. Install agentmemory globally:
   ```bash
   npm install -g agentmemory
   ```

2. Start agentmemory server:
   ```bash
   agentmemory
   ```

3. Install iii-sdk in your project:
   ```bash
   pip install iii-sdk
   # or if using venv:
   .venv/bin/pip install iii-sdk
   ```

4. Update configuration (see above)

5. Verify connection:
   ```bash
   curl http://localhost:3111/agentmemory/health
   ```

## Usage Example

See `examples/coordination_usage.py` for complete examples.

```python
from ccg_collab.coordination.config import CollabConfig

# Get coordination provider (automatically selects backend from config)
config = CollabConfig()
coord = config.get_coordination_provider()

# Acquire exclusive lock
acquired = coord.acquire_lock("resource-id", "agent-name", 60.0)
if acquired:
    # Do work
    coord.release_lock("resource-id", "agent-name")

# Send signal to other agents
coord.send_signal("event-type", {"data": "value"}, "target-agent")

# Wait for signal (with timeout)
signal = coord.wait_signal("event-type", 10.0)
```

## Backend Comparison

| Feature | Filesystem | agentmemory |
|---------|-----------|-------------|
| Locks | Atomic (mkdir) | Distributed leases with TTL |
| Signals | Polling-based | Real-time pub/sub |
| Actions | File-based queue | Priority-ranked queue |
| Cross-machine | ❌ Local only | ✅ Distributed |
| Performance | Fast (local FS) | Network latency |
| Dependencies | None | iii-engine + iii-sdk |
