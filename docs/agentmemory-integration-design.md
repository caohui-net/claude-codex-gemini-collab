# agentmemory Integration Design for claude-codex-gemini-collab

**Version**: 1.0  
**Date**: 2026-06-07  
**Status**: Design Phase

## Executive Summary

This document proposes integrating agentmemory's multi-agent coordination primitives and cross-platform memory sharing into the claude-codex-gemini-collab project. The integration will enhance the project's coordination capabilities while maintaining backward compatibility with the existing filesystem-based protocol.

**Core Value Proposition**:
- Upgrade from file locks to distributed leases
- Add pub/sub messaging via signals
- Enable cross-platform agent participation (Cursor, Copilot, etc.)
- Improve memory consolidation across collaboration sessions
- Maintain existing filesystem-based state for compatibility

---

## 1. Current Architecture Analysis

### 1.1 Existing Coordination Mechanisms

**State Management**:
- Filesystem: `.omc/collaboration/`
- State snapshot: `state.json`
- Event log: `events.jsonl` (append-only, source of truth)
- Tasks: `tasks/TASK-*.md`
- Artifacts: `artifacts/`

**Synchronization**:
- File locks: `locks/journal.lock` (atomic mkdir)
- Lock protocol: acquire → validate → write → release
- Limitation: Local filesystem only, no distributed support

**Agent Coordination**:
- Handoff: via event log (`handoff_requested` event)
- Task claiming: atomic claim procedure with lock
- Discussion: multi-round with consensus detection
- Limitation: Synchronous, polling-based, no pub/sub

**Memory Model**:
- Session-scoped: each collaboration is independent
- No cross-session memory consolidation
- No cross-platform memory sharing

### 1.2 Integration Points Identified

| Component | Current Implementation | agentmemory Enhancement | Priority |
|-----------|------------------------|-------------------------|----------|
| Locking | File-based (`mkdir`) | Lease-based (distributed) | High |
| Messaging | Event log polling | Signals (pub/sub) | High |
| Task Queue | File-based task claiming | Actions (async queue) | Medium |
| Cross-Platform | Claude/Codex/Gemini only | +Cursor, Copilot, OpenCode | Medium |
| Memory | Session-scoped | 4-tier consolidation | Low |

---

## 2. Integration Architecture

### 2.1 Hybrid Architecture (Recommended)

```
┌─────────────────────────────────────────────────┐
│     Agent Clients (Claude/Codex/Gemini/...)    │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│           collab Python Scripts Layer           │
│  - collab.py  - collab_discuss.py              │
│  - collab_task.py  - collab_event.py           │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│         Coordination Abstraction Layer          │
│  (新增) Adapts between filesystem & agentmem   │
└─────────────────────────────────────────────────┘
        ▼                              ▼
┌────────────────────┐    ┌────────────────────────┐
│  Filesystem State  │    │  agentmemory Client    │
│  (existing, v1)    │    │  (optional, v2)        │
│                    │    │                        │
│ - events.jsonl     │    │ - Leases               │
│ - state.json       │    │ - Signals              │
│ - locks/*.lock     │    │ - Actions              │
│ - tasks/*.md       │    │ - Cross-platform mem   │
└────────────────────┘    └────────────────────────┘
                                     ▼
                          ┌────────────────────────┐
                          │ agentmemory Server     │
                          │ (localhost:3111)       │
                          └────────────────────────┘
```

### 2.2 Coordination Abstraction Layer

**Purpose**: Provide a unified API that works with both filesystem (v1) and agentmemory (v2) backends.

**Interface**:

```python
# ccg_collab/coordination.py

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from enum import Enum

class CoordinationBackend(Enum):
    FILESYSTEM = "filesystem"
    AGENTMEMORY = "agentmemory"

class CoordinationProvider(ABC):
    """Abstract coordination provider interface"""
    
    @abstractmethod
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        """Acquire a lock/lease on a resource"""
        pass
    
    @abstractmethod
    def release_lock(self, resource: str, agent: str) -> bool:
        """Release a lock/lease"""
        pass
    
    @abstractmethod
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        """Send a signal to agents (pub/sub)"""
        pass
    
    @abstractmethod
    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for a signal with timeout"""
        pass
    
    @abstractmethod
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        """Enqueue an action for an agent"""
        pass
    
    @abstractmethod
    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        """Claim next action from queue"""
        pass
```

### 2.3 Backend Implementations

**Filesystem Backend** (existing, v1):

```python
class FilesystemCoordination(CoordinationProvider):
    """Filesystem-based coordination (existing behavior)"""
    
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        # Current mkdir-based locking
        lock_path = Path(f".omc/collaboration/locks/{resource}.lock")
        # ... existing implementation
    
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        # Fallback: append to events.jsonl with signal type
        # Polling-based, no real pub/sub
        pass
    
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        # Fallback: create task file
        # No queue semantics, just task creation
        pass
```

**agentmemory Backend** (new, v2):

```python
class AgentMemoryCoordination(CoordinationProvider):
    """agentmemory-based coordination (enhanced)"""
    
    def __init__(self, server_url: str = "http://localhost:3111"):
        self.client = AgentMemoryClient(server_url)
    
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        # Use agentmemory lease_acquire
        return self.client.lease_acquire(
            resource_id=resource,
            holder_id=agent,
            ttl=timeout
        )
    
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        # Use agentmemory signal_send (real pub/sub)
        self.client.signal_send(
            signal_type=signal,
            payload=payload,
            target_agent=target
        )
    
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        # Use agentmemory action_enqueue
        self.client.action_enqueue(
            action_type=action,
            payload=payload,
            assigned_to=target
        )
```

---

## 3. Feature Enhancements

### 3.1 Distributed Leases (Priority: High)

**Problem**: Current file locks only work on local filesystem, not reliable on NFS, no TTL support.

**Solution**: Use agentmemory leases.

**Implementation**:

```python
# ccg_collab/locking.py

class LockManager:
    def __init__(self, backend: CoordinationBackend = CoordinationBackend.FILESYSTEM):
        if backend == CoordinationBackend.AGENTMEMORY:
            self.provider = AgentMemoryCoordination()
        else:
            self.provider = FilesystemCoordination()
    
    def acquire_journal_lock(self, agent: str) -> bool:
        """Acquire journal lock with automatic TTL"""
        return self.provider.acquire_lock(
            resource="journal",
            agent=agent,
            timeout=30.0  # Auto-release after 30s if holder crashes
        )
```

**Benefits**:
- Automatic lease expiry (no stale locks)
- Distributed coordination support
- Lease renewal for long operations
- Dead lock detection

### 3.2 Signal-Based Coordination (Priority: High)

**Problem**: Current handoff polling is inefficient, agents must poll events.jsonl.

**Solution**: Use agentmemory signals for pub/sub messaging.

**Implementation**:

```python
# ccg_collab/signals.py

class SignalCoordinator:
    def __init__(self, backend: CoordinationBackend):
        self.provider = get_coordination_provider(backend)
    
    def notify_handoff(self, from_agent: str, to_agent: str, task_id: str):
        """Send handoff signal to target agent"""
        self.provider.send_signal(
            signal="handoff",
            payload={"task_id": task_id, "from": from_agent},
            target=to_agent
        )
    
    def wait_for_handoff(self, agent: str, timeout: float = 60.0):
        """Wait for incoming handoff signal"""
        signal = self.provider.wait_signal("handoff", timeout)
        if signal:
            return signal["payload"]["task_id"]
        return None
```

**Benefits**:
- Real-time notifications (no polling)
- Lower latency handoffs
- Reduced filesystem I/O
- Scalable to more agents

### 3.3 Action Queue (Priority: Medium)

**Problem**: Current task claiming is synchronous, no async work queue.

**Solution**: Use agentmemory actions for async task distribution.

**Implementation**:

```python
# ccg_collab/actions.py

class ActionQueue:
    def __init__(self, backend: CoordinationBackend):
        self.provider = get_coordination_provider(backend)
    
    def delegate_task(self, task_id: str, to_agent: str, priority: int = 0):
        """Add task to agent's work queue"""
        self.provider.enqueue_action(
            action="task",
            payload={"task_id": task_id, "priority": priority},
            target=to_agent
        )
    
    def get_next_task(self, agent: str):
        """Claim next task from own queue"""
        action = self.provider.claim_action(agent)
        if action:
            return action["payload"]["task_id"]
        return None
```

**Benefits**:
- Async task distribution
- Priority-based scheduling
- Fair work distribution
- Backpressure handling

### 3.4 Cross-Platform Extension (Priority: Medium)

**Problem**: Current collab only supports Claude/Codex/Gemini.

**Solution**: Use agentmemory's cross-platform memory to include Cursor, Copilot, etc.

**Implementation**:

```python
# ccg_collab/agents.py

SUPPORTED_AGENTS = {
    "claude": {"cli": "claude-code", "type": "anthropic"},
    "codex": {"cli": "codex", "type": "openai"},
    "gemini": {"cli": "gemini", "type": "google"},
    # New agents via agentmemory
    "cursor": {"cli": "cursor", "type": "vscode"},
    "copilot": {"cli": "gh copilot", "type": "github"},
    "opencode": {"cli": "opencode", "type": "community"}
}

def register_agent(agent_name: str, agent_config: Dict[str, str]):
    """Register new agent type with agentmemory"""
    if using_agentmemory():
        agentmemory_client.register_agent(agent_name, agent_config)
```

**Benefits**:
- Unified collab across all AI code assistants
- Shared memory across platforms
- Larger developer ecosystem
- Flexible agent participation

---

## 4. Migration Strategy

### 4.1 Phased Rollout

**Phase 0: Foundation** (Week 1)
- [ ] Create coordination abstraction layer
- [ ] Implement FilesystemCoordination (wrap existing code)
- [ ] Add backend selection config
- [ ] Unit tests for both backends

**Phase 1: agentmemory Integration** (Week 2)
- [ ] Implement AgentMemoryCoordination
- [ ] Add agentmemory client wrapper
- [ ] Integration tests
- [ ] Fallback/degradation handling

**Phase 2: Enhanced Features** (Week 3-4)
- [ ] Replace file locks with leases
- [ ] Add signal-based handoff
- [ ] Implement action queue
- [ ] Cross-platform agent registration

**Phase 3: Production Hardening** (Week 5)
- [ ] Error handling and retry logic
- [ ] Monitoring and observability
- [ ] Performance testing
- [ ] Documentation

### 4.2 Backward Compatibility

**Guarantee**: Existing collab workflows must work unchanged.

**Strategy**:
1. Default backend: `FILESYSTEM` (no breaking change)
2. Opt-in agentmemory: via config flag
3. Graceful degradation: if agentmemory unavailable, fall back to filesystem
4. Migration path: run both backends in parallel during transition

**Configuration**:

```json
// .claude/settings.json
{
  "ccgCollab": {
    "coordinationBackend": "filesystem",  // or "agentmemory"
    "agentmemory": {
      "enabled": false,
      "serverUrl": "http://localhost:3111",
      "fallbackToFilesystem": true
    }
  }
}
```

### 4.3 Feature Flags

```python
# ccg_collab/config.py

class CollabConfig:
    def __init__(self):
        settings = load_settings()
        ccg_config = settings.get("ccgCollab", {})
        
        self.backend = ccg_config.get("coordinationBackend", "filesystem")
        self.agentmemory_enabled = ccg_config.get("agentmemory", ).get("enabled", False)
        self.agentmemory_url = ccg_config.get("agentmemory", {}).get("serverUrl", "http://localhost:3111")
        self.fallback = ccg_config.get("agentmemory", {}).get("fallbackToFilesystem", True)
    
    def get_coordination_provider(self) -> CoordinationProvider:
        if self.backend == "agentmemory" and self.agentmemory_enabled:
            try:
                return AgentMemoryCoordination(self.agentmemory_url)
            except ConnectionError:
                if self.fallback:
                    logger.warning("agentmemory unavailable, falling back to filesystem")
                    return FilesystemCoordination()
                raise
        return FilesystemCoordination()
```

---

## 5. Technical Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| agentmemory server crashes during collab | High | Medium | Fallback to filesystem backend, retry logic |
| Lease expiry too short, holder still working | Medium | Medium | Configurable TTL, lease renewal for long ops |
| Signal delivery failure | Medium | Low | Retry with exponential backoff, fallback to event log |
| Cross-platform agents incompatible | Low | Medium | Agent capability negotiation protocol |
| Performance regression | Medium | Low | Benchmark before/after, keep filesystem fast path |

---

## 6. Success Metrics

**Technical Metrics**:
- [ ] Lock acquisition latency <50ms (P95)
- [ ] Signal delivery latency <100ms (P95)
- [ ] Fallback activation time <1s
- [ ] Zero data loss during backend switch
- [ ] Backward compatibility: 100% existing tests pass

**Feature Metrics**:
- [ ] Handoff latency reduced by 80%
- [ ] Support for ≥2 new agent types (Cursor, Copilot)
- [ ] Cross-platform memory sharing working
- [ ] Stale lock incidents reduced to zero

**User Experience Metrics**:
- [ ] Setup time ≤5 minutes
- [ ] Zero breaking changes for existing users
- [ ] Documentation complete for new features
- [ ] ≥3 successful cross-platform collaborations

---

## 7. Open Questions

1. **Memory consolidation**: Should we consolidate collab history into agentmemory's 4-tier memory model, or keep sessions independent?
   - **Recommendation**: Phase 2+ feature, keep sessions independent initially

2. **Event log migration**: Should events.jsonl be synchronized to agentmemory's memory store?
   - **Recommendation**: One-way sync (events → memories) as optional Phase 3 feature

3. **Cross-platform protocol**: How to handle capability differences between agents (e.g., Cursor can't execute Python scripts)?
   - **Recommendation**: Agent capability manifest + negotiation protocol

4. **Lease TTL defaults**: What's the right balance between auto-cleanup and operation safety?
   - **Recommendation**: 30s default, configurable per operation, with renewal API

5. **Signal ordering**: Do we need ordered signal delivery guarantees?
   - **Recommendation**: No ordering guarantees initially, add if needed

---

## 8. Next Steps

1. **Immediate** (This Week):
   - [ ] Review and approve this design
   - [ ] Set up agentmemory server for testing
   - [ ] Create coordination abstraction layer skeleton

2. **Short-Term** (Next 2 Weeks):
   - [ ] Implement Phase 0 (Foundation)
   - [ ] Implement Phase 1 (agentmemory Integration)
   - [ ] Begin Phase 2 (Enhanced Features)

3. **Medium-Term** (Next Month):
   - [ ] Complete Phase 2
   - [ ] Complete Phase 3 (Production Hardening)
   - [ ] Alpha testing with Cursor integration

---

## Appendix A: agentmemory API Mapping

| collab Concept | Current Implementation | agentmemory API | Notes |
|----------------|------------------------|-----------------|-------|
| Lock | `mkdir locks/X.lock` | `lease_acquire(X)` | TTL support, auto-cleanup |
| Handoff | Event log + polling | `signal_send("handoff", ...)` | Real-time, pub/sub |
| Task Queue | File-based task claiming | `action_enqueue()`, `action_claim()` | Priority, fair distribution |
| Agent Registry | Hardcoded list | `register_agent()` | Dynamic, extensible |
| Memory | Session-scoped state | `memory_save()`, `memory_recall()` | Cross-session, 4-tier |

---

**Document Owner**: Claude (main), Codex, Gemini  
**Last Updated**: 2026-06-07  
**Status**: Awaiting Review
