# Priority 2a Implementation Plan

**Status:** Ready to implement
**Consensus:** Claude + Codex agreed (2026-05-30)

## Scope

Add `--base-dir` flag and upward search for `.omc/collaboration/` to all CLI scripts.

## Design Decisions

### Path Resolution Functions

```python
# scripts/collab_paths.py

def resolve_existing_base_dir(base_dir=None, start_dir=None):
    """
    For non-init commands.
    Resolution: --base-dir -> upward .omc/collaboration search -> fail
    """
    pass

def resolve_init_base_dir(base_dir=None, start_dir=None):
    """
    For init command.
    Resolution: --base-dir -> existing upward state -> git root -> cwd
    Prints selected base and source (--base-dir/existing/git/cwd)
    """
    pass

def add_base_dir_arg(parser):
    """Add --base-dir argument to argparse parser."""
    pass
```

### Behavior

**Non-init commands** (task, claim, complete, status, validate, repair, event):
- `--base-dir` specified → use it
- No `--base-dir` → search upward for `.omc/collaboration/`
- Not found → fail with: `No .omc/collaboration directory found from {cwd} upward. Run init or pass --base-dir.`

**Init command**:
- `--base-dir` specified → use it
- No `--base-dir` → search upward for existing `.omc/collaboration/`
- Not found → try git root
- Not in git → use cwd
- Print: `Initializing at {path} (source: {--base-dir|existing|git|cwd})`
- Avoid nested state: reuse existing parent state if found

## Implementation Tasks

### 1. Create collab_paths.py
- [x] `resolve_existing_base_dir(base_dir, start_dir)`
- [x] `resolve_init_base_dir(base_dir, start_dir)`
- [x] `add_base_dir_arg(parser)`
- [x] Helper: `find_git_root(start_dir)`
- [x] Helper: `find_upward_collaboration(start_dir)`

### 2. Update CLI Scripts (5 files)
- [x] `collab_init.py` - use `resolve_init_base_dir()`
- [x] `collab_task.py` - use `resolve_existing_base_dir()`
- [x] `collab_event.py` - use `resolve_existing_base_dir()`
- [x] `collab_status.py` - use `resolve_existing_base_dir()`
- [x] `collab_validate.py` - use `resolve_existing_base_dir()`

### 3. Update SKILL.md
- [x] Remove lines 93-95 (git root, project markers, global fallback)
- [x] Remove lines 97-99 (global index)
- [x] Keep lines 91-92 (--base-dir, upward search)
- [x] Update resolution order section to match implementation

### 4. Add Tests
- [x] Command from repo root
- [x] Command from nested subdir
- [x] `--base-dir` override
- [x] Non-init failure outside initialized state
- [x] Init inside git repo with no existing state
- [x] Init inside nested dir with existing state above
- [x] Init avoids creating nested state

### 5. Production-Readiness Fixes (Post-Codex Review)
- [x] Add --base-dir validation in `resolve_existing_base_dir()`
- [x] Add test for --base-dir validation behavior
- [x] Add test for git-root init behavior
- [x] Add test for nested CLI command execution

## Verification

- [x] All 18 existing tests pass
- [x] New tests pass (12 new tests added)
- [x] Total: 30/30 tests passing
- [ ] Manual smoke test from nested directory
- [x] SKILL.md matches implementation
- [x] Codex review completed - 2 issues identified and fixed

## Deferred (Not in Priority 2a)

- Project markers (package.json, etc.)
- Global directory fallback
- Global index (~/.omc/collaboration/index.json)
