# agentmemory Integration Roadmap - Executable Plan

**Version**: 1.0  
**Date**: 2026-06-07  
**Owner**: Claude (main)  
**Status**: Ready for Execution

## Quick Reference

**Total Estimated Time**: 4-5 weeks  
**Prerequisites**: agentmemory server, Python 3.10+, existing collab project  
**Risk Level**: Medium (backward compatibility maintained)

---

## Phase 0: Environment Setup & Validation

**Duration**: 1-2 days  
**Goal**: Verify agentmemory works and is compatible with collab project

### Step 0.1: Install agentmemory

**Commands**:
```bash
# Install agentmemory globally
npm install -g @agentmemory/agentmemory

# Verify installation
agentmemory --version
# Expected output: 0.x.x

# Start server
agentmemory
# Expected: Server running on http://localhost:3111
```

**Acceptance Criteria**:
- [ ] agentmemory command available
- [ ] Server starts without errors
- [ ] Health endpoint responds: `curl http://localhost:3111/health`

**Verification**:
```bash
# Test health check
curl http://localhost:3111/health
# Expected: {"status":"ok",...}

# Test MCP connection
agentmemory connect claude-code
# Expected: MCP server registered
```

**Rollback**: `npm uninstall -g @agentmemory/agentmemory`

---

### Step 0.2: Verify MCP Proxy Mode

**Commands**:
```bash
# Check MCP tools count
# Should show 53 tools in proxy mode, 7 in standalone

# Test a core tool
curl -X POST http://localhost:3111/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool":"memory_status","args":{}}'
```

**Acceptance Criteria**:
- [ ] 53 tools visible (not 7)
- [ ] `memory_status` tool responds
- [ ] No authentication errors

**Rollback**: Kill agentmemory server, remove MCP connection

---

### Step 0.3: Create Test agentmemory Client

**Commands**:
```bash
cd /home/caohui/projects/claude-codex-gemini-collab

# Create test client
cat > tests/test_agentmemory_client.py << 'EOF'
import requests

class AgentMemoryClient:
    def __init__(self, url="http://localhost:3111"):
        self.url = url
    
    def health_check(self):
        r = requests.get(f"{self.url}/health")
        return r.status_code == 200
    
    def lease_acquire(self, resource_id, holder_id, ttl=30):
        r = requests.post(f"{self.url}/api/lease/acquire", json={
            "resource_id": resource_id,
            "holder_id": holder_id,
            "ttl": ttl
        })
        return r.status_code == 200
    
    def signal_send(self, signal_type, payload, target=None):
        r = requests.post(f"{self.url}/api/signal/send", json={
            "signal_type": signal_type,
            "payload": payload,
            "target": target
        })
        return r.status_code == 200

# Test
client = AgentMemoryClient()
print(f"Health: {client.health_check()}")
EOF

# Run test
python3 tests/test_agentmemory_client.py
```

**Acceptance Criteria**:
- [ ] Client connects successfully
- [ ] Health check returns True
- [ ] No connection errors

**Verification**:
```bash
python3 tests/test_agentmemory_client.py
# Expected: Health: True
```

**Rollback**: `rm tests/test_agentmemory_client.py`

---

## Phase 1: Coordination Abstraction Layer

**Duration**: 3-5 days  
**Goal**: Create abstraction layer supporting both backends

### Step 1.1: Create Coordination Interface

**Commands**:
```bash
# Create coordination module
mkdir -p ccg_collab/coordination
touch ccg_collab/coordination/__init__.py

cat > ccg_collab/coordination/provider.py << 'EOF'
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum

class CoordinationBackend(Enum):
    FILESYSTEM = "filesystem"
    AGENTMEMORY = "agentmemory"

class CoordinationProvider(ABC):
    @abstractmethod
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        pass
    
    @abstractmethod
    def release_lock(self, resource: str, agent: str) -> bool:
        pass
    
    @abstractmethod
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        pass
    
    @abstractmethod
    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        pass
    
    @abstractmethod
    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        pass
EOF
```

**Acceptance Criteria**:
- [ ] Module created
- [ ] Interface compiles without errors
- [ ] All abstract methods defined

**Verification**:
```bash
python3 -c "from ccg_collab.coordination.provider import CoordinationProvider; print('OK')"
# Expected: OK
```

**Rollback**: `rm -rf ccg_collab/coordination`

---

### Step 1.2: Implement Filesystem Backend

**Commands**:
```bash
cat > ccg_collab/coordination/filesystem.py << 'EOF'
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from .provider import CoordinationProvider

class FilesystemCoordination(CoordinationProvider):
    def __init__(self, base_dir: str = ".omc/collaboration"):
        self.base_dir = Path(base_dir)
        self.locks_dir = self.base_dir / "locks"
        self.signals_dir = self.base_dir / "signals"
        self.actions_dir = self.base_dir / "actions"
        
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.actions_dir.mkdir(parents=True, exist_ok=True)
    
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        lock_path = self.locks_dir / f"{resource}.lock"
        try:
            lock_path.mkdir(exist_ok=False)
            lock_data = {"agent": agent, "acquired_at": time.time()}
            (lock_path / "data.json").write_text(json.dumps(lock_data))
            return True
        except FileExistsError:
            return False
    
    def release_lock(self, resource: str, agent: str) -> bool:
        lock_path = self.locks_dir / f"{resource}.lock"
        if lock_path.exists():
            import shutil
            shutil.rmtree(lock_path)
            return True
        return False
    
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        signal_file = self.signals_dir / f"{signal}_{time.time()}.json"
        signal_data = {"type": signal, "payload": payload, "target": target}
        signal_file.write_text(json.dumps(signal_data))
    
    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        # Polling-based implementation (fallback)
        start = time.time()
        while time.time() - start < timeout:
            for sig_file in self.signals_dir.glob(f"{signal}_*.json"):
                data = json.loads(sig_file.read_text())
                sig_file.unlink()
                return data
            time.sleep(0.1)
        return None
    
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        action_file = self.actions_dir / f"{target}_{action}_{time.time()}.json"
        action_data = {"action": action, "payload": payload, "target": target}
        action_file.write_text(json.dumps(action_data))
    
    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        for action_file in sorted(self.actions_dir.glob(f"{agent}_*.json")):
            data = json.loads(action_file.read_text())
            action_file.unlink()
            return data
        return None
EOF
```

**Acceptance Criteria**:
- [ ] FilesystemCoordination compiles
- [ ] All methods implemented
- [ ] Backward compatible with existing locks

**Verification**:
```bash
python3 << 'EOF'
from ccg_collab.coordination.filesystem import FilesystemCoordination

coord = FilesystemCoordination()
assert coord.acquire_lock("test", "claude", 30.0)
assert coord.release_lock("test", "claude")
print("✓ Filesystem backend works")
EOF
```

**Rollback**: `rm ccg_collab/coordination/filesystem.py`

---

### Step 1.3: Implement agentmemory Backend

**Commands**:
```bash
cat > ccg_collab/coordination/agentmemory.py << 'EOF'
import requests
from typing import Optional, Dict, Any
from .provider import CoordinationProvider

class AgentMemoryCoordination(CoordinationProvider):
    def __init__(self, server_url: str = "http://localhost:3111"):
        self.url = server_url
        self._verify_connection()
    
    def _verify_connection(self):
        try:
            r = requests.get(f"{self.url}/health", timeout=2)
            r.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"agentmemory server unavailable: {e}")
    
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        r = requests.post(f"{self.url}/api/lease/acquire", json={
            "resource_id": resource,
            "holder_id": agent,
            "ttl": int(timeout)
        }, timeout=5)
        return r.status_code == 200
    
    def release_lock(self, resource: str, agent: str) -> bool:
        r = requests.post(f"{self.url}/api/lease/release", json={
            "resource_id": resource,
            "holder_id": agent
        }, timeout=5)
        return r.status_code == 200
    
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        requests.post(f"{self.url}/api/signal/send", json={
            "signal_type": signal,
            "payload": payload,
            "target_agent": target
        }, timeout=5)
    
    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        r = requests.post(f"{self.url}/api/signal/wait", json={
            "signal_type": signal,
            "timeout": int(timeout)
        }, timeout=timeout + 2)
        if r.status_code == 200:
            return r.json()
        return None
    
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        requests.post(f"{self.url}/api/action/enqueue", json={
            "action_type": action,
            "payload": payload,
            "assigned_to": target
        }, timeout=5)
    
    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        r = requests.post(f"{self.url}/api/action/claim", json={
            "agent_id": agent
        }, timeout=5)
        if r.status_code == 200:
            return r.json()
        return None
EOF
```

**Acceptance Criteria**:
- [ ] AgentMemoryCoordination compiles
- [ ] Connection validation works
- [ ] All methods implemented

**Verification**:
```bash
# Requires agentmemory server running
python3 << 'EOF'
from ccg_collab.coordination.agentmemory import AgentMemoryCoordination

try:
    coord = AgentMemoryCoordination()
    print("✓ agentmemory backend works")
except ConnectionError as e:
    print(f"⚠ agentmemory server not running: {e}")
EOF
```

**Rollback**: `rm ccg_collab/coordination/agentmemory.py`

---

### Step 1.4: Create Config Manager

**Commands**:
```bash
cat > ccg_collab/coordination/config.py << 'EOF'
import json
from pathlib import Path
from typing import Optional
from .provider import CoordinationBackend, CoordinationProvider
from .filesystem import FilesystemCoordination
from .agentmemory import AgentMemoryCoordination

class CollabConfig:
    def __init__(self, settings_path: str = ".claude/settings.json"):
        self.settings_path = Path(settings_path)
        self.settings = self._load_settings()
        self.ccg_config = self.settings.get("ccgCollab", {})
    
    def _load_settings(self) -> dict:
        if self.settings_path.exists():
            return json.loads(self.settings_path.read_text())
        return {}
    
    @property
    def backend(self) -> CoordinationBackend:
        backend_str = self.ccg_config.get("coordinationBackend", "filesystem")
        return CoordinationBackend(backend_str)
    
    @property
    def agentmemory_enabled(self) -> bool:
        return self.ccg_config.get("agentmemory", {}).get("enabled", False)
    
    @property
    def agentmemory_url(self) -> str:
        return self.ccg_config.get("agentmemory", {}).get("serverUrl", "http://localhost:3111")
    
    @property
    def fallback_enabled(self) -> bool:
        return self.ccg_config.get("agentmemory", {}).get("fallbackToFilesystem", True)
    
    def get_coordination_provider(self) -> CoordinationProvider:
        if self.backend == CoordinationBackend.AGENTMEMORY and self.agentmemory_enabled:
            try:
                return AgentMemoryCoordination(self.agentmemory_url)
            except ConnectionError as e:
                if self.fallback_enabled:
                    import logging
                    logging.warning(f"agentmemory unavailable, falling back to filesystem: {e}")
                    return FilesystemCoordination()
                raise
        return FilesystemCoordination()
EOF
```

**Acceptance Criteria**:
- [ ] Config manager loads settings
- [ ] Backend selection works
- [ ] Fallback logic implemented

**Verification**:
```bash
python3 << 'EOF'
from ccg_collab.coordination.config import CollabConfig

config = CollabConfig()
provider = config.get_coordination_provider()
print(f"✓ Using backend: {type(provider).__name__}")
EOF
```

**Rollback**: `rm ccg_collab/coordination/config.py`

---

## Phase 2: Integration into Existing Scripts

**Duration**: 5-7 days  
**Goal**: Replace file locks with coordination layer

### Step 2.1: Update collab_event.py Lock Acquisition

**Before**:
```python
# Old code in collab_event.py
lock_path = Path(".omc/collaboration/locks/journal.lock")
try:
    lock_path.mkdir(exist_ok=False)
    # ... work ...
finally:
    shutil.rmtree(lock_path)
```

**After**:
```python
# New code
from ccg_collab.coordination.config import CollabConfig

config = CollabConfig()
provider = config.get_coordination_provider()

if provider.acquire_lock("journal", agent_name, 30.0):
    try:
        # ... work ...
    finally:
        provider.release_lock("journal", agent_name)
```

**Commands**:
```bash
# Backup original
cp scripts/collab_event.py scripts/collab_event.py.backup

# Apply changes
# (Edit collab_event.py to use coordination provider)
```

**Acceptance Criteria**:
- [ ] Lock acquisition uses provider
- [ ] Backward compatibility maintained
- [ ] All existing tests pass

**Verification**:
```bash
# Run existing tests
python3 -m pytest tests/ -k "test_event"
# Expected: All tests pass
```

**Rollback**: `mv scripts/collab_event.py.backup scripts/collab_event.py`

---

### Step 2.2: Add Signal-Based Handoff

**Commands**:
```bash
cat > ccg_collab/coordination/signals.py << 'EOF'
from typing import Optional
from .config import CollabConfig

class SignalCoordinator:
    def __init__(self):
        self.config = CollabConfig()
        self.provider = self.config.get_coordination_provider()
    
    def notify_handoff(self, from_agent: str, to_agent: str, task_id: str):
        self.provider.send_signal(
            signal="handoff",
            payload={"task_id": task_id, "from": from_agent},
            target=to_agent
        )
    
    def wait_for_handoff(self, agent: str, timeout: float = 60.0) -> Optional[str]:
        signal = self.provider.wait_signal("handoff", timeout)
        if signal and signal.get("payload"):
            return signal["payload"].get("task_id")
        return None
EOF

# Add to collab_event.py
# After handoff_requested event is appended, send signal
```

**Acceptance Criteria**:
- [ ] Handoff signal sent after event
- [ ] Target agent receives notification
- [ ] Fallback to polling if signal unavailable

**Verification**:
```bash
# Test handoff with signals
python3 << 'EOF'
from ccg_collab.coordination.signals import SignalCoordinator

coord = SignalCoordinator()
coord.notify_handoff("claude", "codex", "TASK-1")
print("✓ Handoff signal sent")
EOF
```

**Rollback**: `rm ccg_collab/coordination/signals.py`

---

## Phase 3: Testing & Validation

**Duration**: 3-5 days  
**Goal**: Comprehensive testing of both backends

### Step 3.1: Unit Tests

**Commands**:
```bash
cat > tests/test_coordination.py << 'EOF'
import pytest
from ccg_collab.coordination.filesystem import FilesystemCoordination
from ccg_collab.coordination.agentmemory import AgentMemoryCoordination

def test_filesystem_lock():
    coord = FilesystemCoordination()
    assert coord.acquire_lock("test", "claude", 30.0)
    assert not coord.acquire_lock("test", "codex", 30.0)  # Already held
    assert coord.release_lock("test", "claude")

def test_filesystem_signal():
    coord = FilesystemCoordination()
    coord.send_signal("test", {"data": "value"}, "codex")
    signal = coord.wait_signal("test", 1.0)
    assert signal is not None
    assert signal["payload"]["data"] == "value"

@pytest.mark.skipif(not agentmemory_available(), reason="agentmemory not running")
def test_agentmemory_lock():
    coord = AgentMemoryCoordination()
    assert coord.acquire_lock("test2", "claude", 30.0)
    assert coord.release_lock("test2", "claude")

def agentmemory_available():
    import requests
    try:
        r = requests.get("http://localhost:3111/health", timeout=1)
        return r.status_code == 200
    except:
        return False
EOF

# Run tests
python3 -m pytest tests/test_coordination.py -v
```

**Acceptance Criteria**:
- [ ] All filesystem tests pass
- [ ] agentmemory tests pass (if server running)
- [ ] Code coverage >80%

**Verification**:
```bash
python3 -m pytest tests/test_coordination.py --cov=ccg_collab.coordination
# Expected: >80% coverage, all tests pass
```

---

### Step 3.2: Integration Tests

**Commands**:
```bash
# Test full handoff workflow with both backends
bash << 'EOF'
# Start agentmemory server
agentmemory &
AGENTMEM_PID=$!

# Test with agentmemory backend
echo '{"ccgCollab":{"coordinationBackend":"agentmemory","agentmemory":{"enabled":true}}}' > .claude/settings.json
python3 scripts/collab_event.py handoff_requested claude TASK-TEST "test handoff" --target-agent codex

# Test with filesystem backend
echo '{"ccgCollab":{"coordinationBackend":"filesystem"}}' > .claude/settings.json
python3 scripts/collab_event.py handoff_requested claude TASK-TEST2 "test handoff" --target-agent codex

# Cleanup
kill $AGENTMEM_PID
EOF
```

**Acceptance Criteria**:
- [ ] Handoff works with both backends
- [ ] No errors in event log
- [ ] State consistent

**Verification**:
```bash
# Check events.jsonl for handoff_requested events
grep handoff_requested .omc/collaboration/events.jsonl | tail -2
# Expected: 2 handoff events
```

---

## Phase 4: Documentation & Release

**Duration**: 2-3 days  
**Goal**: Complete documentation and announce release

### Step 4.1: Update README

**Commands**:
```bash
# Add agentmemory integration section to README.md
cat >> README.md << 'EOF'

## agentmemory Integration (Optional)

Enable enhanced coordination features with agentmemory:

### Setup
```bash
npm install -g @agentmemory/agentmemory
agentmemory
```

### Configuration
Add to `.claude/settings.json`:
```json
{
  "ccgCollab": {
    "coordinationBackend": "agentmemory",
    "agentmemory": {
      "enabled": true,
      "serverUrl": "http://localhost:3111",
      "fallbackToFilesystem": true
    }
  }
}
```

### Features
- Distributed leases (auto-expiry, no stale locks)
- Real-time signal notifications
- Cross-platform agent support (Cursor, Copilot, etc.)

See `docs/agentmemory-integration-design.md` for details.
EOF
```

**Acceptance Criteria**:
- [ ] README updated
- [ ] Configuration examples added
- [ ] Feature list documented

---

### Step 4.2: Create Migration Guide

**Commands**:
```bash
cat > docs/agentmemory-migration-guide.md << 'EOF'
# Migration Guide: Filesystem → agentmemory

## For Existing Users

Your existing collab workflows will continue to work unchanged. agentmemory is optional.

## Enable agentmemory

1. Install: `npm install -g @agentmemory/agentmemory`
2. Start server: `agentmemory`
3. Update settings:
   ```json
   {
     "ccgCollab": {
       "coordinationBackend": "agentmemory",
       "agentmemory": {"enabled": true}
     }
   }
   ```
4. Restart Claude Code session

## Fallback Behavior

If agentmemory server is unavailable, collab automatically falls back to filesystem backend.

## Verification

```bash
python3 -c "from ccg_collab.coordination.config import CollabConfig; print(CollabConfig().get_coordination_provider())"
# Should show: AgentMemoryCoordination
```
EOF
```

**Acceptance Criteria**:
- [ ] Migration guide created
- [ ] Clear instructions for opt-in
- [ ] Rollback procedure documented

---

## Success Criteria

### Technical
- [ ] Both backends functional
- [ ] All existing tests pass
- [ ] No breaking changes
- [ ] Fallback mechanism works
- [ ] Performance: lock acquisition <50ms (P95)

### Documentation
- [ ] Design doc complete
- [ ] Roadmap complete (this doc)
- [ ] Migration guide complete
- [ ] README updated
- [ ] API docs generated

### Testing
- [ ] Unit test coverage >80%
- [ ] Integration tests pass
- [ ] Manual testing with Codex/Gemini
- [ ] Cross-platform test (at least 1 additional agent)

---

## Rollback Plan

### Complete Rollback
```bash
# 1. Remove coordination layer
rm -rf ccg_collab/coordination

# 2. Restore original scripts
for script in collab_event.py collab_discuss.py collab_task.py; do
    if [ -f "scripts/${script}.backup" ]; then
        mv "scripts/${script}.backup" "scripts/${script}"
    fi
done

# 3. Remove config
sed -i '/ccgCollab/d' .claude/settings.json

# 4. Stop agentmemory
pkill -f agentmemory

# 5. Verify
python3 scripts/collab_status.py
```

### Partial Rollback (Keep Layer, Disable agentmemory)
```json
{
  "ccgCollab": {
    "coordinationBackend": "filesystem"
  }
}
```

---

## Monitoring & Observability

### Health Checks
```bash
# Check coordination backend
python3 -c "from ccg_collab.coordination.config import CollabConfig; print(CollabConfig().backend)"

# Check agentmemory server
curl http://localhost:3111/health

# Check lock state
ls -la .omc/collaboration/locks/
```

### Performance Metrics
```bash
# Measure lock acquisition time
time python3 -c "from ccg_collab.coordination.config import CollabConfig; CollabConfig().get_coordination_provider().acquire_lock('test', 'claude', 30)"
```

---

**Roadmap Status**: Ready for Phase 0  
**Next Review**: After Phase 1 completion  
**Owner**: Claude (main), with Codex/Gemini support
