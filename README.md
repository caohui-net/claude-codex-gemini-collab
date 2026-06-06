# Claude-Codex-Gemini Collaboration

Tri-model collaboration protocol for autonomous multi-agent project construction.

## Overview

This skill enables Claude to orchestrate Codex and Gemini collaboration via shared filesystem state, supporting:

- Independent analysis (avoiding anchoring bias)
- Task lifecycle management (create, claim, handoff, complete)
- Multi-agent discussion with consensus detection
- Execution-verification loop for approved consensus
- Automated iteration with feedback-driven retry
- Event sourcing with atomic operations
- State validation and repair

## Installation

### 1. Sync to all installation paths

```bash
python3 scripts/sync_skill_install.py
```

This syncs SKILL.md to:
- `.omc/skills/claude-codex-gemini-collab/`
- `~/.claude/skills/claude-codex-gemini-collab/`
- `~/.omc/skills/claude-codex-gemini-collab/`

### 2. Configure skillOverrides (required)

Add to `.claude/settings.local.json`:

```json
{
  "skillOverrides": {
    "ccg": "off"
  }
}
```

This disables OMC's built-in `ccg` skill to avoid conflicts.

### 3. Restart Claude Code session

Changes take effect after restart.

### 4. Verify activation

```bash
python3 scripts/collab_doctor.py
```

## Usage

### Unified entry point (recommended)

```bash
python3 scripts/collab.py help      # Show all commands
python3 scripts/collab.py status    # Check collaboration state
python3 scripts/collab.py doctor    # Run diagnostics
python3 scripts/collab.py task create "description"
python3 scripts/collab.py handoff gemini TASK-1  # Handoff to target agent
```

### Direct script usage

```bash
/claude-codex-gemini-collab init          # Initialize collaboration
/claude-codex-gemini-collab task "..."    # Create task
/claude-codex-gemini-collab status        # Check state
```

For handoff, use the script directly:
```bash
python3 scripts/collab_event.py handoff_requested <agent> <TASK-ID> "handoff to <target>" --target-agent <target>
```

Examples:
```bash
# Claude to Codex
python3 scripts/collab_event.py handoff_requested claude TASK-1 "handoff to codex" --target-agent codex

# Claude to Gemini
python3 scripts/collab_event.py handoff_requested claude TASK-1 "handoff to gemini" --target-agent gemini

# Gemini to Codex
python3 scripts/collab_event.py handoff_requested gemini TASK-2 "handoff to codex" --target-agent codex
```

## Discussion Features

Multi-agent discussion orchestration with consensus detection and state persistence.

### Usage

```bash
# Start a discussion (recommended format)
python3 scripts/collab.py discuss --topic "Your discussion topic" --max-rounds 3

# Check discussion status
python3 scripts/collab.py discuss status TASK-ID

# Resume interrupted discussion
python3 scripts/collab.py discuss resume TASK-ID

# View discussion history
python3 scripts/collab.py discuss history TASK-ID
```

### Compatibility

Legacy format still supported for backward compatibility:
```bash
python3 scripts/collab_discuss.py discuss TASK-ID "topic" --participants codex,gemini
```

### Consensus Semantics

- **all_responded**: True when all required participants completed (not failed/skipped)
- **consensus_reached**: True when all participants agree (consensus=true in responses)
- **blocking_issues**: List of issues preventing consensus

## Execution Features

Execute approved consensus with verification and automated iteration.

### Usage

```bash
# Execute consensus (requires user approval by default)
python3 scripts/collab_execute.py .omc/collaboration/tasks/TASK-ID/consensus.json

# Execute with auto-iteration on rejection (max 3 iterations)
python3 scripts/collab_execute.py .omc/collaboration/tasks/TASK-ID/consensus.json --auto-iterate

# Custom iteration limit
python3 scripts/collab_execute.py .omc/collaboration/tasks/TASK-ID/consensus.json --auto-iterate --max-iterations 5

# Auto-approve execution (skip confirmation)
python3 scripts/collab_execute.py .omc/collaboration/tasks/TASK-ID/consensus.json --auto-approve
```

### Execution Workflow

1. **Pre-execution validation**: Path security, required fields, consensus integrity
2. **User approval**: Interactive confirmation (unless `--auto-approve`)
3. **Git snapshot**: Capture working tree state for rollback
4. **Task execution**: Parse consensus and write files
5. **Post-execution audit**: Collect changed files and evidence
6. **Verification**: Run tests, check build, validate results
7. **Review report**: Generate status (approved/rejected/needs_changes)
8. **Auto-iteration**: If rejected and `--auto-iterate`, create new discussion with feedback

### Review Status

- **approved**: Execution successful, all verification passed
- **rejected**: Critical issues found, needs fixes before proceeding
- **needs_changes**: Minor issues, can iterate with adjustments

### Test Coverage

- 5 core scenarios validated (see `scripts/test_all_responded.py`)
- Recovery semantics tested (see `scripts/test_scan.py`)

## Recovery Features

The discussion system supports crash recovery and resume capabilities.

### Recovery Commands

```bash
# Scan for incomplete tasks (runs automatically on daemon startup)
python3 scripts/collab_discuss.py scan

# Check discussion status
python3 scripts/collab_discuss.py status TASK-ID

# Resume interrupted discussion
python3 scripts/collab_discuss.py resume TASK-ID

# Retry failed participants
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

### Common Scenarios

**Daemon restart:**
```bash
python3 scripts/collab_discuss.py scan              # Find incomplete tasks
python3 scripts/collab_discuss.py status TASK-ID    # Check specific task
python3 scripts/collab_discuss.py resume TASK-ID    # Resume from checkpoint
```

**Daemon crash or user interruption:**
```bash
python3 scripts/collab_discuss.py status TASK-ID    # Check state
python3 scripts/collab_discuss.py resume TASK-ID    # Resume from checkpoint
```

**Agent timeout:**
```bash
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

### State Persistence

- **Discussion state**: Persisted to `.omc/collaboration/state/{TASK-ID}.json`
- **Daemon state**: In-memory only (not persisted across daemon restarts)

**Limitation:** If daemon restarts, use discussion-level recovery commands (`status`, `resume`) to continue.

For detailed recovery documentation, see `.omc/collaboration/recovery-guide.md`.

## Workspace Resolution

All commands support `--base-dir` to specify the collaboration workspace root explicitly:

```bash
python3 scripts/collab_status.py --base-dir /path/to/workspace
```

**Non-init commands** (status, validate, task, etc.):
1. Use `--base-dir` if specified
2. Search upward for `.omc/collaboration/`
3. Fail with diagnostic if not found

**Init command**:
1. Use `--base-dir` if specified
2. Reuse existing upward `.omc/collaboration/` (avoids nested state)
3. Use git root if inside git repo
4. Fall back to current directory

This allows running commands from any nested directory within a workspace.

## Requirements

- Python 3.8+
- Codex CLI (`npm install -g @openai/codex`)
- Gemini CLI (`npm install -g @google/gemini-cli`)
- oh-my-claudecode plugin

## Structure

```
.
├── SKILL.md              # Skill definition
├── README.md             # This file
├── assets/
│   └── protocol.md       # Collaboration protocol
└── scripts/
    ├── collab_init.py    # Initialize collaboration
    ├── collab_task.py    # Task management
    ├── collab_event.py   # Event logging
    ├── collab_status.py  # State inspection
    └── collab_validate.py # Validation/repair
```

## Troubleshooting

### Skill not activating after restart

**Symptoms:** Claude still uses `omc ask` instead of the skill.

**Diagnosis:**
```bash
python3 scripts/collab_doctor.py
```

**Common issues:**

1. **Version mismatch across paths**
   ```bash
   # Re-sync all paths
   python3 scripts/sync_skill_install.py
   ```

2. **skillOverrides not configured**
   ```bash
   # Check configuration
   cat .claude/settings.local.json | grep skillOverrides
   
   # If missing, add:
   # {"skillOverrides": {"ccg": "off"}}
   ```

3. **Session not restarted**
   - Exit Claude Code completely
   - Restart and test with: `/collab status`

4. **YAML syntax error in SKILL.md**
   ```bash
   # Verify frontmatter
   head -20 SKILL.md
   ```

### Permission errors during sync

**Symptoms:** `sync_skill_install.py` fails with permission denied.

**Fix:**
```bash
# Ensure directories exist and are writable
mkdir -p ~/.claude/skills/claude-codex-gemini-collab
mkdir -p ~/.omc/skills/claude-codex-gemini-collab
chmod -R u+w ~/.claude/skills ~/.omc/skills
```

### settings.local.json doesn't exist

**Fix:**
```bash
# Create with skillOverrides
cat > .claude/settings.local.json << 'EOF'
{
  "skillOverrides": {
    "ccg": "off"
  }
}
EOF
```

### Verification after fix

```bash
# 1. Run diagnostics
python3 scripts/collab_doctor.py

# 2. Restart Claude Code session

# 3. Test skill activation
/collab status
# Should show: 🛠️ [Skill: Collab] handling request...
```

## Known Limitations

Current MVP release (v0.1.1) has the following known constraints:

### Discussion State Persistence
- Daemon state is memory-based and requires discussion-level recovery on restart
- Persistent state available via `.omc/collaboration/state/*.json` files
- Recovery commands: `collab.py discuss scan`, `collab.py discuss resume TASK-ID`

### Protocol Coverage
- WebSocket integration has MVP TODOs for real-time collaboration
- Daemon enhancements (health checks, log rotation) deferred to v0.2.0 backlog

### Testing
- 77 tests passing (core functionality validated)
- Additional regression coverage planned for v0.2.0

### Future Enhancements
- Phase 4B (daemon reliability): deferred to backlog
- Phase 4D (new collaboration features): deferred to backlog

See CHANGELOG.md for detailed release notes and roadmap.

## Version

0.3.1 - Skill activation fixes with diagnostic tools
