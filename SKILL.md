---
name: claude-codex-gemini-collab
displayName: Multi-Agent Collab
aliases: [collab, ccg, tricollab]
description: Claude-Codex-Gemini collaboration protocol operations - init, task management, state validation
version: 0.3.0
---

# Claude-Codex-Gemini Collaboration Skill

Provides deterministic operations for Claude-Codex-Gemini tri-model collaboration via shared filesystem state.

## When to Use

**Trigger on strong intent phrases (collaboration object + action verb):**

Chinese examples:
- 让Claude和Codex一起讨论
- 启动多模型协作
- 交给Codex/Gemini处理
- 创建协作任务
- 查看协作状态

English examples:
- start Claude Codex collaboration
- handoff to Codex
- create a collaboration task
- check collaboration status
- multi-model discussion

**Do NOT trigger on:**
- 我们讨论一下X (general conversation)
- discuss the implementation (general conversation)
- 帮我review一下 (may be code review)

**Graded trigger behavior:**
- Read-only (auto-execute): `status`, `validate`
- Mutating (requires clear intent): `task`, `claim`, `complete`, handoff
- High-risk (requires slash command): `repair`

**Slash command always takes priority:** `/claude-codex-gemini-collab` or aliases `/collab`, `/ccg`

## Commands

```
/claude-codex-gemini-collab init
/claude-codex-gemini-collab validate
/claude-codex-gemini-collab status
/claude-codex-gemini-collab task "<description>"
/claude-codex-gemini-collab claim <TASK-ID>
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
- Print error message with details
- Return non-zero exit code
- Suggest repair command if applicable

## Directory Structure

**Collaboration state (fixed location):**
- `.omc/collaboration/` - Protocol-defined collaboration state
  - `state.json`, `events.jsonl` - Event-sourced state
  - `tasks/`, `artifacts/`, `locks/` - Workflow data
  - `protocol.md` - Protocol documentation

**Dialogue artifacts (dynamic location):**
- `.omc/artifacts/ask/` - Codex/Gemini response artifacts
  - Location varies: project root when in project, `~/.omc/artifacts/ask/default/` otherwise
  - Not part of collaboration protocol state
  - Used by `/oh-my-claudecode:ask` skill

**Important:** These are separate concerns. Collaboration state is fixed and protocol-defined. Dialogue artifacts are advisory skill outputs with dynamic storage.

**Workspace root resolution (for collaboration state):**

Resolution order:
1. `--base-dir` explicit specification
2. Upward search for `.omc/collaboration/`
3. Upward search for git root
4. Upward search for project markers (package.json, etc.)
5. Global directory fallback

**Global index:**
- `~/.omc/collaboration/index.json` records workspace locations
- Not source of truth, only for discovery assistance

**Principle:** Workspace root is dynamic, internal structure is fixed.

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

## Notes

- Normal workflow scripts use atomic operations (mkdir for locks, temp+rename for state)
- Repair tool is an exception: does not acquire locks or use temp+rename
- All timestamps are UTC ISO-8601
- Event IDs allocated from max(events.jsonl), not state.json
- Filesystem must support atomic mkdir (local or NFSv4)
