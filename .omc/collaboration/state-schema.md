# Discussion Task State Schema

## Purpose
Persistent state for discussion tasks to enable crash recovery and resume.

## Storage Location
`.omc/collaboration/state/{task_id}.json`

## Schema Structure

```json
{
  "task_id": "TASK-XXX",
  "topic": "discussion topic text",
  "status": "pending|running|completed|failed|cancelled",
  "created_at": "ISO8601 timestamp",
  "updated_at": "ISO8601 timestamp",
  "completed_at": "ISO8601 timestamp or null",
  
  "rounds": [
    {
      "round_number": 1,
      "status": "pending|running|completed|failed",
      "started_at": "ISO8601 timestamp",
      "completed_at": "ISO8601 timestamp or null",
      
      "participants": [
        {
          "agent": "codex|gemini",
          "status": "pending|running|completed|failed",
          "started_at": "ISO8601 timestamp",
          "completed_at": "ISO8601 timestamp or null",
          "response_file": "path to artifact file",
          "parsed_response": {
            "consensus": true|false|null,
            "decision": "text",
            "blocking_issues": ["issue1", "issue2"],
            "reasoning": "text"
          },
          "error": {
            "type": "timeout|format_error|execution_failed|daemon_crash",
            "message": "error details",
            "timestamp": "ISO8601"
          }
        }
      ],
      
      "consensus_check": {
        "all_responded": true|false,
        "consensus_reached": true|false|null,
        "decision": "unified decision text or null",
        "blocking_issues": ["remaining issues"]
      }
    }
  ],
  
  "final_consensus": {
    "reached": true|false,
    "decision": "final decision text",
    "blocking_issues": [],
    "round_number": 3
  },
  
  "failures": [
    {
      "timestamp": "ISO8601",
      "round_number": 2,
      "agent": "codex",
      "error_type": "timeout|format_error|execution_failed|daemon_crash|file_write_failed",
      "error_message": "details",
      "recoverable": true|false
    }
  ],
  
  "retry_attempts": [
    {
      "attempt_number": 1,
      "timestamp": "ISO8601",
      "round_number": 2,
      "agent": "codex",
      "reason": "timeout on previous attempt"
    }
  ],
  
  "artifacts": {
    "directory": ".omc/collaboration/artifacts/",
    "files": [
      "TASK-XXX-discuss-r1-codex-timestamp.md",
      "TASK-XXX-discuss-r1-gemini-timestamp.md"
    ]
  }
}
```

## State Transitions

### Task Status
- `pending` → `running` (first round starts)
- `running` → `completed` (consensus reached)
- `running` → `failed` (max rounds exceeded or unrecoverable error)
- `running` → `cancelled` (user cancellation)

### Round Status
- `pending` → `running` (first agent starts)
- `running` → `completed` (all agents responded and consensus checked)
- `running` → `failed` (unrecoverable error)

### Participant Status
- `pending` → `running` (agent execution starts)
- `running` → `completed` (response received and parsed)
- `running` → `failed` (error occurred)

## Recovery Semantics

### On Daemon Crash
1. Read state file for task
2. Find last completed participant in current round
3. Resume from next pending participant
4. Do NOT replay completed participants

### On Format Error
1. Mark participant as failed
2. Record error in failures array
3. Continue to next participant (don't block round)
4. Report format errors in final summary

### On Timeout
1. Mark participant as failed with timeout error
2. Increment retry_attempts if under limit
3. Retry same participant or skip based on policy

### On File Write Failure
1. Mark as failed with file_write_failed error
2. Log to stderr
3. Continue discussion (state preserved in memory)

## Checkpoint Strategy

### When to Write
- After each participant completes (atomic checkpoint)
- After each round completes
- On task completion
- On error/failure

### Atomic Write
```python
temp_file = state_file.with_suffix('.tmp')
temp_file.write_text(json.dumps(state, indent=2))
temp_file.rename(state_file)  # Atomic on POSIX
```

## Resume Command

```bash
python3 scripts/collab_discuss.py resume TASK-XXX
```

Behavior:
1. Read state file
2. Check task status
3. If running: resume from last checkpoint
4. If completed: show results
5. If failed: show error and suggest retry

## Status Command

```bash
python3 scripts/collab_discuss.py status TASK-XXX
```

Shows:
- Task status
- Current round
- Completed/pending participants
- Consensus status
- Recent errors
