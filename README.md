# Claude-Codex-Gemini Collaboration

Tri-model collaboration protocol for autonomous multi-agent project construction.

## Overview

This skill enables Claude, Codex, and Gemini to collaborate autonomously via shared filesystem state, supporting:

- Independent analysis (avoiding anchoring bias)
- Task lifecycle management (create, claim, handoff, complete)
- Event sourcing with atomic operations
- State validation and repair

## Installation

Copy to Claude Code skills directory:

```bash
cp -r . ~/.claude/skills/claude-codex-gemini-collab/
```

## Usage

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

## Version

0.3.0 - Tri-model protocol with locked event/state validation
