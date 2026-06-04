# Project Summary

## Latest Changes

### Phase-3D Task #34: E2E Tests (2026-06-04)

**Status:** ✅ Complete

**Objective:** Add E2E test coverage for recovery scenarios and discussion consensus logic.

**Tests Created:**
- `scripts/test_resume_partial_failure.py` - Resume without retry skips failed participants
- `scripts/test_resume_retry.py` - Resume with --retry-failed re-executes failed participant
- `scripts/test_discussion_consensus.py` - Both participants agree, task completes
- `scripts/test_discussion_no_consensus.py` - Disagreement triggers next round

**Verification:** All 4 tests passing

**Related:**
- Task #33 (fix all_responded semantics) already complete with 5 existing tests
- Part of Phase-3D cleanup plan

---

### Skill Specification Priority Fix (2026-06-03)

**Status:** ✅ Prompt layer fix implemented

**Issue:** User explicit skill specification被系统自动判断覆盖

**Root Cause (Codex consensus):**
- 路由模型缺少"显式用户指定"与"系统推断选择"优先级隔离
- 显式技能被后续分类器、ask兜底、last-writer-wins逻辑覆盖

**Solution Implemented:**
- Added explicit skill invocation priority rule to `~/.claude/CLAUDE.md`
- Rule: When user explicitly specifies skill, invoke immediately before any analysis
- Pattern matching: "use X", "使用X技能", "invoke X", "用X"

**Documentation:**
- `.omc/collaboration/artifacts/skill-specification-priority-fix.md` - Full analysis

**Discussion:**
- 3 rounds with Codex (consensus achieved)
- Gemini timeout (proxy 500 errors)

**Next Steps:**
- Test in new sessions
- Consider implementation-layer fix if prompt insufficient

---

### rmux/tmux Integration (2026-06-02)

**Status:** ✅ Complete and merged to master

**Feature:** Optional process isolation via tmux sessions for agent execution.

**Changes:**
- Added `use_tmux` parameter to `run_codex()` and `run_gemini()`
- New `rmux_utils.py`: Detection and version checking
- New `run_in_tmux()`: Isolated session execution with exit code capture
- Environment variable `CCG_USE_TMUX=true` enables tmux for all agents
- Full backward compatibility (default: `use_tmux=False`)

**Files Modified:**
- `scripts/agent_cli.py` - Added tmux execution path
- `scripts/collab_discuss.py` - Added env var support
- `scripts/rmux_utils.py` - Detection utilities (new)
- `scripts/test_rmux_integration.py` - Integration tests (new)
- `docs/rmux-integration-summary.md` - Implementation docs (new)

**Testing:**
- 3/3 rmux integration tests passing
- Portable tests (no unconditional assertions)

**Review Process:**
- 5 rounds of code review (v1-v5)
- Consensus reached with Codex and Gemini in v5 round 1
- Production ready approval from both agents

**Key Fixes Applied:**
- UnboundLocalError: `task_id` initialization in both functions
- Stdin injection: Unique EOF marker per execution
- Detection: Functional test instead of binary check
- Test portability: Removed unconditional availability assertions

**Commit:** `feat: add optional rmux/tmux integration for process isolation`

---

## Project Status

**Current Phase:** Feature enhancement complete
**Next Steps:** User testing and feedback
