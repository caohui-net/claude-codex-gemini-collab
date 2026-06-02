# Token Optimization - File Reference Mode

## Overview

File reference mode reduces token usage by ~91% per discussion round by storing context in files and passing only file paths to agents.

## Configuration

### Environment Variable

**CCG_USE_FILE_REF** - Enable/disable file reference mode

- **Default:** `true` (enabled)
- **Disable:** `export CCG_USE_FILE_REF=false`

### Behavior

**Enabled (default):**
- Topic, history, and artifacts saved to `.omc/collaboration/context/`
- Agents receive file paths instead of full content
- Typical prompt: ~90 tokens (vs ~1100 tokens inline)

**Disabled:**
- Full content embedded in prompts (backward compatible)
- Use when debugging or if agents cannot read files

## Implementation

### Files

- **scripts/collab_discuss.py:632** - Default value configuration
- **scripts/collab_discuss.py:50-90** - `build_discussion_prompt()` with `context_file` parameter
- **scripts/collab_discuss.py:save_discussion_context()** - Context file generation

### Context File Format

```markdown
# Discussion Context

**Task:** DISCUSS-TASK-ID
**Round:** N

## Topic

[topic content]

## Previous Discussion

[compressed history]

## Referenced Artifacts

- artifact1.md
- artifact2.md
```

### Storage Location

Context files: `.omc/collaboration/context/{task-id}-r{round}-context.md`

Rationale: Internal collaboration state, not project deliverables (consensus: architecture discussion)

## Testing

**scripts/test_file_ref.py** - 3/3 tests passing
- Inline mode (backward compatible)
- File reference mode
- Context file creation

## Token Savings

| Mode | Topic | History | Artifacts | Total |
|------|-------|---------|-----------|-------|
| Inline | ~100 | ~1000 | ~20 | ~1120 |
| File Ref | ~20 (path) | ~20 (path) | ~20 (path) | ~90 |
| **Savings** | | | | **~91%** |

## Consensus Decision

Based on discussion DISCUSS-讨论协议TOKEN优化-当前每轮需传递完整TOPIC-HISTORY-1780423432:

- Default enable CCG_USE_FILE_REF
- Implement incremental delivery (future)
- Structured history compression (future)
- Auto-fallback on read failure (future)

## Related

- `.omc/collaboration/artifacts/` - Discussion artifacts
- `scripts/test_file_ref.py` - Test coverage
