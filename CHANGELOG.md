# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.3.0] - 2026-06-02

### Fixed

- **Bug #3: UX Validation** - Added stdout message validation in tests for soft/hard limit UX
- **Bug #4: State Persistence** - Added `limits` field to task state for persisting `max_rounds` and `hard_max_rounds`
- **Resume Boundary** - Fixed resume to check last round status, starting from next round if completed
- **Wrapper Conclude Routing** - Added `conclude` to `collab.py` discuss_subcommands
- **Conclude Blocker** - Fixed `run_conclude()` to allow manual conclusion after hard limit without consensus

### Changed

- Resume now reads limits from state instead of hardcoded values (backward compatible)
- Test coverage expanded to verify UX messages, not just exit codes

### Notes

- **Production-ready consensus**: Codex and Gemini confirmed all critical bugs resolved
- 84 tests passing
- All fixes based on multi-round discussions with Codex/Gemini identifying issues

## [0.2.1] - 2026-06-02

### Fixed

- **Bug #1: Resume Continuation** - Fixed `run_resume()` to pass `hard_max_rounds=10` allowing discussions to continue past soft limit to hard limit.
- **Bug #2: Hard Limit Enforcement** - Fixed discussion loop to cap at `min(max_rounds, hard_max_rounds)` preventing exceeding hard limit when `max_rounds > hard_max_rounds`.

### Added

- **Test Coverage** - Added `tests/test_soft_hard_limits.py` with 2 tests for soft/hard limit behavior (84 total tests passing).

## [0.2.0] - 2026-06-02

### Added

- **P2-1: all_responded Observability** - Added `actual_responded` and `expected_count` fields to `consensus_check` in task state. Enables debugging of partial-response scenarios (e.g., 2/3 participants completed vs 3/3 expected).
- **P2-1: Partial-Response Tests** - Added `tests/test_partial_response.py` with coverage for both partial (2/3) and full (2/2) participant response scenarios.
- **P0-1: Decision Persistence Test** - Added `tests/test_decision_persistence.py` validating final_consensus.decision extraction from participant responses.
- **P0-2: Terminal State Test** - Added `tests/test_terminal_state.py` verifying no-consensus terminal state transitions.
- **P0-3: Conclude Path Test** - Added `tests/test_conclude.py` validating manual conclude command behavior.
- **P0-4: Routing Validation Test** - Added `tests/test_routing.py` verifying SKILL.md trigger pattern documentation.

### Changed

- **P2-3: Documentation Consistency** - Clarified throughout documentation that Claude orchestrates Codex/Gemini rather than being an equal participant in discussions.
- **P2-3: Known Limitations** - Added comprehensive Known Limitations section to README documenting daemon state persistence, protocol coverage, testing status, and future enhancements.
- **P2-3: Phase 4A Cleanup** - Removed outdated "Phase 4A documentation TODO" references from README.

### Fixed

- **P0-1: Decision Content Extraction** - Fixed `complete_round()` to extract actual decision content from participant responses instead of hardcoded "Consensus reached" placeholder.

## [0.1.1] - 2026-06-02

### Fixed

- **P1-2: Decision Persistence** - Discussion consensus now captures actual decision content from participant responses instead of placeholder "Consensus reached" text. Enables reliable decision retrieval from task state.
- **P1-3: Terminal State** - Discussions that reach max rounds without consensus now properly transition to 'completed' status with `final_consensus.reached=false` instead of remaining in 'running' state indefinitely.
- **P1-4: Protocol Event Consistency** - Added `discussion_started` and `discussion_concluded` events per `assets/protocol.md` specification. Improves event flow auditing and history reliability.
- **STATUS_MAP Bug** - Added `discussion_started` and `discussion_concluded` to `STATUS_MAP` in `collab_state.py`. Fixes ownership corruption where protocol events were defaulting to `status=in_progress` instead of ownership-neutral `discussion` status.

## [0.1.0] - 2026-06-01

### MVP Release

Multi-agent collaboration framework for Claude, Codex, and Gemini with event-sourced state management and consensus-driven discussion orchestration.

#### Features

- **Event-Sourced Collaboration Protocol**
  - Atomic state management with journal-based event log
  - Task lifecycle: create, claim, handoff, complete
  - State validation and repair tools

- **Multi-Agent Discussion System**
  - Consensus detection across multiple rounds
  - Automatic TASK-ID generation from topic
  - Unified entry point: `python3 scripts/collab.py discuss --topic "..."`
  - Recovery and resume capabilities
  - Structured artifact output

- **Test Coverage**
  - 20 passing tests covering core functionality
  - all_responded semantics validation
  - --topic parameter integration tests
  - Discussion recovery scenarios

#### Phase Completion

- Phase 3C: Hardening (all_responded semantics, recovery)
- Phase 3D: Cleanup (documentation, test coverage)
- Phase 4A: Discussion MVP (--topic parameter, unified entry point)

#### Known Limitations

- Daemon state is memory-based (requires discussion-level recovery on restart)
- WebSocket integration has MVP TODOs
- Phase 4B (daemon enhancements) and Phase 4D (new features) deferred to backlog

#### Breaking Changes

- Removed `collab_discuss_wrapper.py` (functionality integrated into `collab_discuss.py`)
- Recommended entry point changed from direct script invocation to `collab.py` router

