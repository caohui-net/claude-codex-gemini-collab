# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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

