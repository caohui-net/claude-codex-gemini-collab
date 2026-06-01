# Changelog

All notable changes to this project will be documented in this file.

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

