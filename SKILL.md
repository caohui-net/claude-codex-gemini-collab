---
name: claude-codex-gemini-collab
displayName: Multi-Agent Collab
aliases: [collab, tricollab]
description: Use when the user wants persistent Claude/Codex/Gemini collaboration state, task creation, claim/complete, or handoff to Codex/Gemini. Prefer this over omc ask for collaboration protocol operations; do not use for one-off advisor questions.
version: 0.4.3
---

# Claude-Codex-Gemini Collaboration Skill

Provides deterministic operations for Claude-Codex-Gemini tri-model collaboration via shared filesystem state.

## Routing Rule

Use this skill when the user asks to:
- start or manage Claude-Codex-Gemini collaboration
- create, claim, complete, validate, or inspect collaboration tasks
- hand off a task to Codex or Gemini using shared `.omc/collaboration/` state

Do not route these requests to `omc ask codex` or `omc ask gemini` unless the user asks for a one-off external opinion/advisor response.

**Examples:**
- "请Codex给我一个一次性review" → `omc ask codex`
- "创建一个协作任务并交给Codex/Gemini处理" → `claude-codex-gemini-collab`
- "查看协作状态/任务归属/事件日志" → `claude-codex-gemini-collab`

## When to Use

**Trigger on strong intent phrases (collaboration object + action verb):**

Chinese examples:
- 让Claude和Codex一起讨论
- 启动多模型协作
- 交给Codex/Gemini处理
- 创建协作任务
- 查看协作状态

English examples:
- start Claude Codex Gemini collaboration
- handoff to Codex
- handoff to Gemini
- create a collaboration task
- check collaboration status
- multi-model discussion
- Gemini claim task
- Gemini complete task

**Do NOT trigger on:**
- 我们讨论一下X (general conversation)
- discuss the implementation (general conversation)
- 帮我review一下 (may be code review)

**Graded trigger behavior:**
- Read-only (auto-execute): `status`, `validate`
- Mutating (requires clear intent): `task`, `claim`, `complete`, handoff
- High-risk (requires slash command): `repair`

**Slash command always takes priority:** `/claude-codex-gemini-collab` or aliases `/collab`, `/tricollab`

## Commands

```
/claude-codex-gemini-collab init
/claude-codex-gemini-collab validate
/claude-codex-gemini-collab status
/claude-codex-gemini-collab task "<description>"
/claude-codex-gemini-collab claim <TASK-ID>
/claude-codex-gemini-collab complete <TASK-ID>
/claude-codex-gemini-collab discuss --topic "<topic>" [--mode fast|full] [--max-rounds 3]
/claude-codex-gemini-collab repair
```

### discuss - Multi-Agent Discussion

**Purpose:** Initiate multi-round discussion where Claude orchestrates Codex and Gemini responses to reach consensus on a topic.

**Trigger:**
- Command: `/claude-codex-gemini-collab discuss --topic "<topic>" [--mode fast|full] [--max-rounds 3]`
- Natural language: "让Codex和Gemini讨论X", "启动讨论：Y", "Claude orchestrate Codex/Gemini discussing X"

**Parameters:**
- `--topic` (required): Discussion topic
- `--mode` (optional): Discussion mode (default: full)
  - `full`: Multi-round persistent discussion with consensus detection (requires init)
  - `fast`: Single-round stateless discussion, ccg-style (no init required)
- `--max-rounds` (optional): Maximum rounds (default: 3, range: 1-10, forced to 1 in fast mode)
- Participants: Codex and Gemini (orchestrated by Claude)

**Prerequisites:**
- `full` mode: Must run `init` first to establish collaboration state
- `fast` mode: No init required (stateless)

**Behavior:**
- Does NOT auto-create task
- Writes discussion artifacts to `.omc/collaboration/artifacts/`
- Returns consensus result or blocking issues

**Example:**
```
/claude-codex-gemini-collab discuss --topic "API设计方案评审" --max-rounds 5
```

**Mode Comparison:**

| Feature | fast mode | full mode |
|---------|-----------|-----------|
| Rounds | Single (1) | Multi (default 3) |
| State | Stateless | Persistent event-sourced |
| Init | Not required | Required |
| Consensus | Claude synthesis | Consensus detection |
| Artifacts | `.omc/collaboration/artifacts/fast/` | `.omc/collaboration/artifacts/` |
| Use case | Quick consultation (ccg-style) | Formal discussion with history |

**vs omc ask:**
- `omc ask`: Single external consultation, one-shot advice
- `discuss --mode=fast`: Replaces ccg, single-round parallel consultation
- `discuss --mode=full`: Multi-round collaborative discussion with consensus detection

**Parallel Execution (v0.4.3+):**

Agents now execute in parallel using ThreadPoolExecutor instead of sequential execution:
- **Before:** Codex (5s) → wait → Gemini (180s) = 185s total
- **After:** max(Codex 5s, Gemini 180s) = 180s total
- Benefits: Faster consensus, non-blocking architecture, better timeout handling

**Gemini Configuration:**

Gemini CLI requires valid API configuration in `~/.gemini/.env`:
```bash
GOOGLE_GEMINI_BASE_URL=<valid-endpoint>
GEMINI_API_KEY=<your-api-key>
GEMINI_MODEL=gemini-3-pro-preview
```

**Known Issue:** If Gemini endpoint returns 404 or times out, discussion will complete with Codex-only results. Check `~/.gemini/.env` if Gemini consistently fails.

**Troubleshooting:**
- Gemini timeout → Check `~/.gemini/.env` endpoint validity
- Only Codex artifacts → Verify Gemini API key and endpoint
- Use `--participants codex` to skip Gemini temporarily

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

**Non-init commands** (status, validate, task, etc.):
1. `--base-dir` explicit specification
2. Upward search for `.omc/collaboration/`
3. Fail with diagnostic if not found

**Init command**:
1. `--base-dir` explicit specification
2. Existing upward `.omc/collaboration/` (reuse, avoid nested state)
3. Git root (if inside git repo)
4. Current working directory

**Principle:** Workspace root is dynamic, internal structure is fixed.

## Implementation

### init

Creates collaboration directory structure and initializes protocol.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_init.py
```

Creates:
- `.omc/collaboration/` directory
- `protocol.md` (from template)
- `state.json` (initialized)
- `events.jsonl` (empty)
- `tasks/`, `artifacts/`, `locks/` subdirectories

### discuss

Orchestrates multi-agent discussion between Codex and Gemini to reach consensus on a topic.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_discuss.py discuss --topic "topic description" [--participants codex,gemini] [--max-rounds 3]
```

**How it works:**
- Script handles ALL agent invocation internally via `agent_cli.py`
- Claude should ONLY execute the script and wait for results
- Do NOT manually spawn agents or use Agent tool
- Script orchestrates rounds, collects responses, detects consensus

Features:
- Auto-initializes collaboration if not found (v0.4.0+)
- Generates task ID from topic if not provided
- Saves discussion artifacts to `.omc/collaboration/artifacts/`
- Generates consensus contract in `.omc/collaboration/tasks/{task_id}/consensus.json`

Subcommands:
- `resume <TASK-ID>`: Resume interrupted discussion
- `status <TASK-ID>`: Show discussion status
- `conclude <TASK-ID> "decision"`: Manually conclude with decision
- `history <TASK-ID>`: Show discussion history
- `scan`: Scan for incomplete discussions

### validate

Runs read-only collaboration journal/state validation.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_validate.py
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
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_status.py [--task TASK-ID]
```

Displays:
- Current workflow status
- Active agent
- Current task
- Recent events
- Any issues detected

With `--task` flag:
- Shows discussion status for specific task
- Displays rounds, agents, and consensus states
- Format: `[Round N] Agent: ✓/✗ (Consensus: Yes/No)`

### task

Creates new collaboration task.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_task.py create "<description>"
```

- Generates task ID
- Creates task document with YAML front matter
- Appends `task_created` event
- Updates state

### claim

Claims an open task (atomic operation).

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_task.py claim <TASK-ID>
```

- Acquires journal lock
- Checks task not already claimed
- Appends `task_claimed` event
- Updates state
- Releases lock

### handoff

Prepares handoff to other agent (filesystem only).

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_event.py handoff_requested <agent> <TASK-ID> "handoff to <target-agent>" --target-agent <target-agent>
```

Example:
```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_event.py handoff_requested claude TASK-1 "handoff to codex" --target-agent codex
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_event.py handoff_requested claude TASK-1 "handoff to gemini" --target-agent gemini
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_event.py handoff_requested gemini TASK-2 "handoff to codex" --target-agent codex
```

- Appends `handoff_requested` event with `details.target_agent`
- Updates state to `waiting`
- Sets active owner to target agent

Does NOT auto-invoke codex/gemini (user must do manually via /oh-my-claudecode:ask).

### complete

Marks task as completed.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_task.py complete <TASK-ID>
```

- Appends `completed` event
- Updates state
- Sets active_agent to none

### repair

Attempts to repair corrupted collaboration state.

```bash
python3 ~/.claude/skills/claude-codex-gemini-collab/scripts/collab_validate.py repair
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
