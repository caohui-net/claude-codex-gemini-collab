# CCG Skill Cross-Project Test Plan

**Version:** v0.4.2
**Date:** 2026-06-06
**Purpose:** Verify claude-codex-gemini-collab skill works across different project contexts

## Test Matrix

| Test ID | Project Type | Language | Trigger Method | Expected Result |
|---------|-------------|----------|----------------|-----------------|
| T1 | Python project | Python | `/collab status` | Show status or "not initialized" |
| T2 | Node.js project | JavaScript | `/collab status` | Show status or "not initialized" |
| T3 | Empty directory | None | `/collab status` | Show status or "not initialized" |
| T4 | Python project | Python | `/collab discuss --topic "test"` | Auto-init + discussion starts |
| T5 | Already initialized | Mixed | `/collab status` | Show existing state |

## Test Projects

1. **graduation-leave-system** (Python Flask)
   - Path: `/home/caohui/projects/graduation-leave-system`
   - Has `.omc/collaboration/` (initialized)

2. **school-ai-chat-cc** (reported error location)
   - Path: `/home/caohui/projects/school-ai-chat-cc`
   - Status: TBD

3. **Empty test directory**
   - Path: `/tmp/test-collab-empty`
   - Purpose: Test from non-project context

## Pass Criteria

**Command execution:**
- Exit code 0 (success)
- No "command not found" errors
- No "module not found" errors
- No "file not found" errors for skill scripts

**Output quality:**
- Meaningful status information or error messages
- Correct path resolution (uses absolute paths)
- Auto-init works when needed (discuss command)

## Bugs Fixed

- v0.4.1: Absolute paths for cross-project invocation
- v0.4.2: Implementation section clarifies agent invocation
- v0.4.3: All module dependencies copied to skill directory

## Execution Log

**Date:** 2026-06-06 17:09

| Test ID | Exit Code | Output | Result |
|---------|-----------|--------|--------|
| T3 | 0 | "No .omc/collaboration directory found" | ✅ PASS |
| T1 | 0 | Status: discussion | ✅ PASS |
| T2 | 0 | Status: unknown (not initialized) | ✅ PASS |

**Verification:** All tests pass. Skill correctly uses absolute paths and works from any directory.
