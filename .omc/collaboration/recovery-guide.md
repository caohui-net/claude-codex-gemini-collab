# Discussion Recovery Guide

## Overview

The discussion system now supports crash recovery and resume. If a discussion is interrupted (daemon crash, network failure, user interruption), you can resume from the last checkpoint.

## Commands

### Status Command

Check the status of a discussion task:

```bash
python3 scripts/collab_discuss.py status TASK-ID
```

**Output:**
- Task status (pending/running/completed/failed)
- Current round and participant status
- Recent failures
- Consensus status (if completed)

**Example:**
```bash
$ python3 scripts/collab_discuss.py status TASK-NEXT-STEP

📊 Task Status: TASK-NEXT-STEP
   Status: running
   Topic: Phase 3C discussion
   Created: 2026-06-01T17:11:57Z

📝 Rounds: 2
   Round 1: completed
      ✓ codex: completed
      ✓ gemini: completed
   Round 2: running
      ✓ codex: completed
      ✗ gemini: failed
         Error: timeout - execution exceeded 180s
```

### Resume Command

Resume an interrupted discussion:

```bash
python3 scripts/collab_discuss.py resume TASK-ID
```

**Behavior:**
- Loads task state from checkpoint
- Skips completed participants
- Continues from pending participants
- Preserves all artifacts

**Example:**
```bash
$ python3 scripts/collab_discuss.py resume TASK-NEXT-STEP

🔄 Resuming TASK-NEXT-STEP from round 2
⏳ [Round 2] Resuming...
✓ [Codex] already completed (skipping)
⏳ [Gemini] analyzing...
```

### Resume with Retry

Retry failed participants:

```bash
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

**Behavior:**
- Resets failed participants to pending
- Re-executes them with the same prompt
- Useful for transient failures (timeout, network issues)

**Example:**
```bash
$ python3 scripts/collab_discuss.py resume TASK-NEXT-STEP --retry-failed

🔄 Resuming TASK-NEXT-STEP from round 2
   Retrying 1 failed participant(s)
⏳ [Round 2] Resuming...
✓ [Codex] already completed (skipping)
⏳ [Gemini] retrying...
```

## Error Types

| Error Type | Description | Recoverable | Action |
|------------|-------------|-------------|--------|
| `execution_failed` | Agent CLI returned non-zero exit code | Maybe | Check agent logs, retry |
| `format_error` | Response missing markers or invalid JSON | No | Check agent output, manual fix |
| `timeout` | Agent execution exceeded timeout | Yes | Retry with --retry-failed |
| `daemon_crash` | Daemon crashed during execution | Yes | Resume automatically |
| `file_write_failed` | Failed to write artifact file | No | Check disk space, permissions |

## Troubleshooting

### Scenario 1: Daemon Crashed

**Symptoms:**
- Discussion interrupted mid-execution
- No response from daemon

**Recovery:**
```bash
# Check task status
python3 scripts/collab_discuss.py status TASK-ID

# Resume from checkpoint
python3 scripts/collab_discuss.py resume TASK-ID
```

### Scenario 2: Agent Timeout

**Symptoms:**
- Agent execution exceeded timeout (default 180s)
- Participant marked as failed with timeout error

**Recovery:**
```bash
# Check status to see which agent timed out
python3 scripts/collab_discuss.py status TASK-ID

# Retry failed participants
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

### Scenario 3: Format Error

**Symptoms:**
- Agent response missing [RESPONSE_START]/[RESPONSE_END] markers
- Participant marked as failed with format_error

**Recovery:**
```bash
# Check artifact file to see raw response
cat .omc/collaboration/artifacts/TASK-ID-discuss-rN-agent-timestamp.md

# If response is valid but markers missing, manual fix needed
# Otherwise, retry
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

### Scenario 4: User Interruption (Ctrl+C)

**Symptoms:**
- User pressed Ctrl+C during discussion
- Discussion stopped mid-round

**Recovery:**
```bash
# State is automatically saved
# Resume from checkpoint
python3 scripts/collab_discuss.py resume TASK-ID
```

## State Files

### Location

Task state files are stored at:
```
.omc/collaboration/state/{TASK-ID}.json
```

### Format

See `.omc/collaboration/state-schema.md` for detailed schema.

**Key fields:**
- `status`: Task status (pending/running/completed/failed)
- `rounds`: Array of round states
- `rounds[].participants`: Array of participant states
- `failures`: Array of failure records
- `artifacts`: List of generated artifact files

### Manual Inspection

```bash
# View task state
cat .omc/collaboration/state/TASK-ID.json | jq .

# Check participant status in current round
cat .omc/collaboration/state/TASK-ID.json | jq '.rounds[-1].participants'

# List failures
cat .omc/collaboration/state/TASK-ID.json | jq '.failures'
```

## Best Practices

1. **Check status before resume**: Always run `status` command first to understand current state
2. **Retry transient failures**: Use `--retry-failed` for timeout and network errors
3. **Preserve artifacts**: Don't delete artifact files, they're needed for resume
4. **Monitor disk space**: State files and artifacts consume disk space
5. **Clean up completed tasks**: Remove state files for completed tasks after verification

## Advanced Usage

### Resume from Specific Round

Not directly supported. To restart from a specific round:
1. Delete state file: `rm .omc/collaboration/state/TASK-ID.json`
2. Start new discussion with same task ID

### Manual State Repair

If state file is corrupted:
1. Backup: `cp .omc/collaboration/state/TASK-ID.json{,.bak}`
2. Edit manually (use schema as reference)
3. Validate: `python3 -c "import json; json.load(open('.omc/collaboration/state/TASK-ID.json'))"`
4. Resume: `python3 scripts/collab_discuss.py resume TASK-ID`

## Limitations

### Discussion-Level Limitations

- Resume only works within same discussion session (same topic, participants)
- Cannot change max_rounds or timeout after discussion starts
- Failed participants are skipped by default (use --retry-failed to retry)
- No automatic retry for format errors (manual intervention required)

### Daemon State Persistence

**Current Status:** Discussion task state is persisted, but Daemon task state is NOT persisted.

**What This Means:**
- **Discussion state** (`.omc/collaboration/state/{TASK-ID}.json`): ✓ Persisted to disk
  - Survives daemon crashes
  - Survives user interruptions
  - Can be resumed with `resume` command
  
- **Daemon task state** (in-memory only): ✗ NOT persisted
  - Lost on daemon restart
  - Lost on system reboot
  - Cannot be recovered after daemon process ends

**Impact:**
- If daemon restarts while a discussion is running, the discussion state is preserved but the daemon loses track of the active task
- Workaround: Use discussion-level recovery commands (`status`, `resume`)
- The daemon will not automatically resume tasks after restart

**Future Enhancement:**
Full Daemon state persistence is planned for a future release. This will enable:
- Automatic task recovery on daemon restart
- Daemon startup scanning to detect incomplete tasks
- Seamless recovery across daemon restarts

## See Also

- State Schema: `.omc/collaboration/state-schema.md`
- Recovery Semantics: `.omc/collaboration/recovery-semantics.md`
- Protocol Documentation: `.omc/collaboration/protocol.md`
