# Discussion Task Recovery Semantics

## Purpose
Define recovery behavior after daemon crash, process interruption, or system failure.

## Core Principles

1. **No Replay**: Never re-execute completed participants
2. **Resume from Checkpoint**: Continue from last successful checkpoint
3. **Preserve Artifacts**: Keep all generated artifacts
4. **Clear Status**: Mark incomplete work as pending/failed

## Recovery Scenarios

### Scenario 1: Daemon Crash During Participant Execution

**State:**
- Round N started
- Participant A completed
- Participant B running (no response saved)
- Participant C pending

**Recovery:**
1. Load task state from `.omc/collaboration/state/{task_id}.json`
2. Check round N status: "running"
3. Check participant B status: "running" (no completed_at)
4. Mark participant B as "failed" with error_type="daemon_crash"
5. Resume from participant C (status="pending")
6. Do NOT re-run participant A

**Implementation:**
```python
def resume_discussion(base_dir, task_id):
    state = load_task_state(base_dir, task_id)
    current_round = len(state["rounds"])
    
    # Find incomplete participants
    for p in state["rounds"][current_round-1]["participants"]:
        if p["status"] == "running":
            # Mark as failed
            fail_participant(state, current_round, p["agent"], 
                           "daemon_crash", "Daemon crashed during execution")
    
    # Resume from pending participants
    pending = get_pending_participants(state, current_round)
    # Continue discussion loop with pending participants
```

### Scenario 2: Format Error (Invalid JSON Response)

**State:**
- Participant responds but JSON is malformed
- Response saved to artifact file

**Recovery:**
1. Mark participant as "failed" with error_type="format_error"
2. Record in failures array
3. Continue to next participant (don't block round)
4. Report format errors in final summary

**Policy:** Format errors are non-blocking. Discussion continues.

### Scenario 3: Timeout

**State:**
- Participant execution exceeds timeout_sec
- No response received

**Recovery:**
1. Mark participant as "failed" with error_type="timeout"
2. Check retry_attempts count
3. If under limit (default: 1 retry): add to retry queue
4. If over limit: skip participant, continue round

**Policy:** One automatic retry per participant per round.

### Scenario 4: User Interruption (Ctrl+C)

**State:**
- User sends SIGINT during discussion
- Current participant may be mid-execution

**Recovery:**
1. Catch SIGINT signal
2. Mark current participant as "failed" with error_type="user_interrupt"
3. Save task state
4. Exit gracefully
5. User can resume with `collab_discuss.py resume TASK-ID`

**Implementation:**
```python
import signal

def handle_interrupt(signum, frame):
    print("\n⚠️  Interrupted by user")
    # Save current state
    save_task_state(base_dir, task_id, task_state)
    print(f"💾 State saved. Resume with: collab_discuss.py resume {task_id}")
    sys.exit(130)

signal.signal(signal.SIGINT, handle_interrupt)
```

### Scenario 5: File Write Failure

**State:**
- Participant completes but artifact write fails
- Response data in memory

**Recovery:**
1. Mark participant as "failed" with error_type="file_write_failed"
2. Log error to stderr
3. Continue discussion (state preserved in memory)
4. Report file write errors in final summary

**Policy:** File write failures are non-blocking. In-memory state is authoritative.

## Resume Command

### Usage
```bash
python3 scripts/collab_discuss.py resume TASK-ID [--retry-failed]
```

### Behavior
1. Load task state from file
2. Check task status:
   - `pending`: Start from round 1
   - `running`: Resume from current round
   - `completed`: Show results, exit
   - `failed`: Show error, suggest retry
3. Find current round and pending participants
4. Resume discussion loop from pending participants
5. Skip completed participants (use existing artifacts)

### Options
- `--retry-failed`: Retry failed participants instead of skipping

## Retry Strategy

### Automatic Retry
- Triggered by: timeout, transient errors
- Limit: 1 retry per participant per round
- Behavior: Re-execute participant with same prompt

### Manual Retry
- Triggered by: `--retry-failed` flag
- Limit: None (user decision)
- Behavior: Re-execute all failed participants

### Skip Strategy
- Triggered by: format errors, unrecoverable errors
- Behavior: Mark as failed, continue to next participant
- Rationale: Don't block discussion on single participant failure

## State Consistency

### Checkpoint Timing
- After participant starts: `status="running"`
- After participant completes: `status="completed"`, artifact saved
- After participant fails: `status="failed"`, error recorded
- After round completes: `status="completed"`, consensus checked

### Atomic Writes
All state writes use temp file + rename for atomicity:
```python
temp_file = state_file.with_suffix('.tmp')
temp_file.write_text(json.dumps(state, indent=2))
temp_file.rename(state_file)  # Atomic on POSIX
```

### Consistency Guarantees
- State file always reflects last successful checkpoint
- Artifacts are immutable once written
- No partial writes (atomic rename)
- No lost updates (temp file pattern)

## Error Classification

| Error Type | Recoverable | Retry | Block Round |
|------------|-------------|-------|-------------|
| timeout | Yes | Auto (1x) | No |
| format_error | No | Manual | No |
| execution_failed | Maybe | Manual | No |
| daemon_crash | Yes | Auto | No |
| user_interrupt | Yes | Manual | Yes |
| file_write_failed | No | No | No |

## Resume Examples

### Example 1: Resume after crash
```bash
# Daemon crashed during round 2
$ python3 scripts/collab_discuss.py resume TASK-NEXT-STEP

🔄 [Skill: Collab] Resuming discussion for TASK-NEXT-STEP
   Status: running, Rounds: 2
   Round 2: codex completed, gemini failed (daemon_crash)
⏳ [Round 2] Resuming...
⏳ [Gemini] analyzing...
```

### Example 2: Resume with retry
```bash
# Retry failed participants
$ python3 scripts/collab_discuss.py resume TASK-NEXT-STEP --retry-failed

🔄 [Skill: Collab] Resuming discussion for TASK-NEXT-STEP
   Retrying 1 failed participant(s)
⏳ [Round 2] Resuming...
⏳ [Gemini] retrying...
```

### Example 3: Resume completed task
```bash
$ python3 scripts/collab_discuss.py resume TASK-NEXT-STEP

✅ Task already completed
   Consensus: true
   Decision: Agree to proceed with Phase 3C-Stability
   Artifacts: .omc/collaboration/artifacts/TASK-NEXT-STEP-discuss-r*
```

## Implementation Checklist

- [x] State schema defined
- [x] Checkpoint functions implemented
- [ ] Resume command implemented
- [ ] Signal handling for interruption
- [ ] Retry logic
- [ ] Error classification
- [ ] Status command
- [ ] Recovery tests
