---
name: claude-codex-gemini-collab
description: Claude-Codex-Gemini collaboration protocol operations - init, task management, state validation
version: 0.3.0
---

# Claude-Codex-Gemini Collaboration Skill

Provides deterministic operations for Claude-Codex-Gemini tri-model collaboration via shared filesystem state.

## When to Use

- User requests Claude-Codex-Gemini collaboration setup
- User wants to create/manage collaboration tasks
- User needs to check collaboration state
- User mentions "multi-model collaboration", "handoff to codex/gemini", "collaboration status"

## Commands

```
/claude-codex-gemini-collab init
/claude-codex-gemini-collab validate
/claude-codex-gemini-collab status
/claude-codex-gemini-collab task "<description>"
/claude-codex-gemini-collab claim <TASK-ID>
/claude-codex-gemini-collab handoff <codex|gemini> <TASK-ID>
/claude-codex-gemini-collab complete <TASK-ID>
/claude-codex-gemini-collab repair
```

## Protocol Rules

**MUST read before any operation:**
- `.omc/collaboration/protocol.md` (if exists)
- Current `state.json` and recent `events.jsonl`

**MUST use scripts for state changes:**
- Never manually write to `events.jsonl` or `state.json`
- Always use provided Python scripts for atomic operations
- Scripts handle: locking, validation, event ID allocation, state consistency

**On failure:**
- Stop immediately
- Create repair artifact in `.omc/collaboration/artifacts/`
- Set `state.status = "needs_repair"` if possible
- Report to user with recovery steps

## Implementation

### init

Creates collaboration directory structure and initializes protocol.

```bash
python3 scripts/collab_init.py
```

Creates:
- `.omc/collaboration/` directory
- `protocol.md` (from template)
- `state.json` (initialized)
- `events.jsonl` (empty)
- `tasks/`, `artifacts/`, `locks/` subdirectories

### validate

Runs read-only collaboration journal/state validation.

```bash
python3 scripts/collab_validate.py
```

Checks:
- `events.jsonl` valid JSONL, no duplicate IDs
- `state.json` valid JSON, last_event_id matches log
- No residual lock entries in `.omc/collaboration/locks/`
- Non-zero exit code on validation failure

This command does not repair or mutate collaboration files.

### status

Shows current collaboration state.

```bash
python3 scripts/collab_status.py
```

Displays:
- Current workflow status
- Active agent
- Current task
- Recent events
- Any issues detected

### task

Creates new collaboration task.

```bash
python3 scripts/collab_task.py create "<description>"
```

- Generates task ID
- Creates task document with YAML front matter
- Appends `task_created` event
- Updates state

### claim

Claims an open task (atomic operation).

```bash
python3 scripts/collab_task.py claim <TASK-ID>
```

- Acquires journal lock
- Checks task not already claimed
- Appends `task_claimed` event
- Updates state
- Releases lock

### handoff

Prepares handoff to other agent (filesystem only).

```bash
python3 scripts/collab_event.py handoff_requested <agent> <TASK-ID> "handoff to <target-agent>"
```

Example:
```bash
python3 scripts/collab_event.py handoff_requested claude TASK-1 "handoff to codex"
```

- Appends `handoff_requested` event
- Updates state to `waiting`
- Outputs: "Next: /oh-my-claudecode:ask codex '<message>'"

Does NOT auto-invoke codex/gemini (user must do manually via /oh-my-claudecode:ask).

### complete

Marks task as completed.

```bash
python3 scripts/collab_task.py complete <TASK-ID>
```

- Appends `completed` event
- Updates state
- Sets active_agent to none

### repair

Attempts to repair corrupted collaboration state.

```bash
python3 scripts/collab_validate.py repair
```

- Backs up current files
- Rebuilds state.json from events.jsonl
- Removes stale locks
- Creates repair artifact

## Notes

- Scripts use atomic operations (mkdir for locks, temp+rename for state)
- All timestamps are UTC ISO-8601
- Event IDs allocated from max(events.jsonl), not state.json
- Filesystem must support atomic mkdir (local or NFSv4)
