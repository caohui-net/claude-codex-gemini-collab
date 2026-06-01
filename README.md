# Claude-Codex-Gemini Collaboration

Tri-model collaboration protocol for autonomous multi-agent project construction.

## Overview

This skill enables Claude, Codex, and Gemini to collaborate autonomously via shared filesystem state, supporting:

- Independent analysis (avoiding anchoring bias)
- Task lifecycle management (create, claim, handoff, complete)
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

## Recovery Features

The discussion system supports crash recovery and resume capabilities.

### Recovery Commands

```bash
# Check discussion status
python3 scripts/collab_discuss.py status TASK-ID

# Resume interrupted discussion
python3 scripts/collab_discuss.py resume TASK-ID

# Retry failed participants
python3 scripts/collab_discuss.py resume TASK-ID --retry-failed
```

### Common Scenarios

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

## Version

0.3.1 - Skill activation fixes with diagnostic tools
