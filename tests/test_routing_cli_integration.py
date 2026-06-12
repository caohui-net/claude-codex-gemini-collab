#!/usr/bin/env python3
"""Integration tests for routing CLI persistence."""

import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ccg_collab" / "scripts"))

from collab_init import init_collaboration
from collab_event import append_event, read_events
from collab_classify import classify_and_route
from collab_audit import trigger_audit
from collab_override import override_routing
from collab_status import show_status


def test_classify_persistence():
    """Test classify appends classify_requested and route_decided events."""
    base = Path(tempfile.mkdtemp(prefix='test-classify-'))
    init_collaboration(base)
    append_event(base, 'task_created', 'claude', 'TASK-1', 'Created task: 优化API逻辑')

    rc = classify_and_route(base, 'TASK-1')
    assert rc == 0, "classify_and_route should return 0 on success"

    events = read_events(base / '.collab' / 'events.jsonl')
    event_types = [e.get('type') for e in events]

    assert 'classify_requested' in event_types, "classify_requested event missing"
    assert 'route_decided' in event_types, "route_decided event missing"
    print("✓ classify_requested and route_decided persisted")


def test_audit_persistence():
    """Test audit appends audit_started event."""
    base = Path(tempfile.mkdtemp(prefix='test-audit-'))
    init_collaboration(base)
    append_event(base, 'task_created', 'claude', 'TASK-2', 'Created task: feature X')

    rc = trigger_audit(base, 'TASK-2')
    assert rc == 0, "trigger_audit should return 0 on success"

    events = read_events(base / '.collab' / 'events.jsonl')
    event_types = [e.get('type') for e in events]

    assert 'audit_started' in event_types, "audit_started event missing"

    # Check audit details
    audit_event = next(e for e in events if e.get('type') == 'audit_started')
    assert audit_event.get('details', {}).get('audit_id') == 'AUDIT-TASK-2'
    print("✓ audit_started persisted with correct details")


def test_override_persistence():
    """Test override appends manual_override event."""
    base = Path(tempfile.mkdtemp(prefix='test-override-'))
    init_collaboration(base)
    append_event(base, 'task_created', 'claude', 'TASK-3', 'Created task: UI fix')

    rc = override_routing(base, 'TASK-3', 'gemini', 'UI specialist needed')
    assert rc == 0, "override_routing should return 0 on success"

    events = read_events(base / '.collab' / 'events.jsonl')
    event_types = [e.get('type') for e in events]

    assert 'manual_override' in event_types, "manual_override event missing"

    # Check override details
    override_event = next(e for e in events if e.get('type') == 'manual_override')
    details = override_event.get('details', {})
    assert details.get('assigned_agent') == 'gemini'
    assert details.get('reason') == 'UI specialist needed'
    print("✓ manual_override persisted with correct details")


def test_full_routing_workflow():
    """Test complete classify → audit → override workflow."""
    base = Path(tempfile.mkdtemp(prefix='test-workflow-'))
    init_collaboration(base)
    append_event(base, 'task_created', 'claude', 'TASK-4', 'Created task: 实现表单验证')

    # Classify
    rc = classify_and_route(base, 'TASK-4')
    assert rc == 0

    # Audit
    rc = trigger_audit(base, 'TASK-4')
    assert rc == 0

    # Override
    rc = override_routing(base, 'TASK-4', 'codex', 'backend logic focus')
    assert rc == 0

    # Verify all events persisted in order
    events = read_events(base / '.collab' / 'events.jsonl')
    event_types = [e.get('type') for e in events]

    expected_order = ['task_created', 'classify_requested', 'route_decided',
                      'audit_started', 'manual_override']
    assert event_types == expected_order, f"Event order mismatch: {event_types}"
    print("✓ Full workflow events persisted in correct order")


def test_status_command():
    """Test status command returns correct state."""
    base = Path(tempfile.mkdtemp(prefix='test-status-'))
    init_collaboration(base)
    append_event(base, 'task_created', 'claude', 'TASK-5', 'Test task')
    classify_and_route(base, 'TASK-5')

    # Status should work without errors
    rc = show_status(str(base))
    assert rc == 0, "show_status should return 0"
    print("✓ Status command works")


def test_error_handling():
    """Test error handling for invalid inputs."""
    base = Path(tempfile.mkdtemp(prefix='test-errors-'))
    init_collaboration(base)

    # Classify non-existent task
    rc = classify_and_route(base, 'NONEXISTENT')
    assert rc == 1, "Should fail for non-existent task"

    # Override with invalid agent
    append_event(base, 'task_created', 'claude', 'TASK-6', 'Test')
    rc = override_routing(base, 'TASK-6', 'invalid_agent', 'test')
    assert rc == 1, "Should fail for invalid agent"

    # Override with empty reason
    rc = override_routing(base, 'TASK-6', 'codex', '')
    assert rc == 1, "Should fail for empty reason"

    print("✓ Error handling works correctly")


if __name__ == "__main__":
    print("Testing routing CLI integration...")
    test_classify_persistence()
    test_audit_persistence()
    test_override_persistence()
    test_full_routing_workflow()
    test_status_command()
    test_error_handling()
    print("\n✓ All CLI integration tests passed!")
