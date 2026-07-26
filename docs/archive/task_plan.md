# TASK-20260607-1157 Plan

Goal: Implement Phase 3 advanced consensus features from `docs/architecture-integration-consensus.md`: semantic conflict detection, cross-project collaboration controls, and a quality metrics dashboard while preserving Phase 1/2 behavior.

## Phases

| Phase | Status | Work |
| --- | --- | --- |
| 1 | complete | Inspect Phase 3 requirements, existing Phase 1/2 implementation, task metadata, and tests |
| 2 | complete | Implement `check_conflicts()` semantic-opposite detection against historical consensus |
| 3 | complete | Implement cross-project controls: namespace, permission, TTL expiry, and version control |
| 4 | complete | Implement quality metrics dashboard: citation rate, action item executability, and history reuse hit rate |
| 5 | complete | Add/update focused tests |
| 6 | complete | Run verification and update task tracking |

## Decisions

- Keep agentmemory integration optional and degrade gracefully when iii/agentmemory is unavailable.
- Follow existing Phase 1/2 patterns in `scripts/collab_discuss.py`, `scripts/models.py`, and `ccg_collab/coordination/agentmemory.py`.
- Do not modify unrelated dirty worktree files.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `pytest -q` / combined explicit test paths hit collection/import problems | Final verification | Used explicit root/package test groups separately; combined root+package script tests have duplicate module basenames and `tests/test_collab_paths.py` is affected by pre-existing `/tmp/.omc/collaboration` |
