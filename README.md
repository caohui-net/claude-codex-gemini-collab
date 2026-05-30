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
python3 scripts/collab_event.py handoff_requested <agent> <TASK-ID> "handoff to <target>"
```

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
