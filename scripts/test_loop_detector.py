#!/usr/bin/env python3
"""
Tests for loop_detector.py

Tests all doom loop detection patterns:
1. Repeated timeouts
2. Identical responses
3. Stalled progress
"""

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from loop_detector import detect_doom_loop, LoopStatus


def create_test_state(state_data: dict, task_id: str = "TEST-TASK-001") -> Path:
    """Create a temporary state file for testing"""
    tmpdir = Path(tempfile.mkdtemp())
    state_dir = tmpdir / ".omc" / "collaboration" / "state"
    state_dir.mkdir(parents=True)

    state_file = state_dir / f"{task_id}.json"
    with open(state_file, "w") as f:
        json.dump(state_data, f)

    return tmpdir


def test_repeated_timeout():
    """Test detection of repeated timeout failures"""
    state = {
        "task_id": "TEST-TASK-001",
        "status": "running",
        "failures": [
            {"agent": "codex", "error_type": "execution_failed", "error_message": "timeout"},
            {"agent": "codex", "error_type": "execution_failed", "error_message": "timeout"},
        ],
        "rounds": []
    }

    tmpdir = create_test_state(state)
    result = detect_doom_loop("TEST-TASK-001", base_dir=tmpdir)

    assert result.is_stuck, "Should detect repeated timeout"
    assert result.pattern == "repeated_timeout"
    assert "codex" in result.suggested_action
    print("✓ test_repeated_timeout passed")


def test_identical_responses():
    """Test detection of identical responses"""
    state = {
        "task_id": "TEST-TASK-002",
        "status": "running",
        "failures": [],
        "rounds": [
            {
                "round_number": 1,
                "status": "completed",
                "participants": [
                    {
                        "agent": "gemini",
                        "status": "completed",
                        "parsed_response": {"decision": "Need more context"}
                    }
                ]
            },
            {
                "round_number": 2,
                "status": "completed",
                "participants": [
                    {
                        "agent": "gemini",
                        "status": "completed",
                        "parsed_response": {"decision": "Need more context"}
                    }
                ]
            }
        ]
    }

    tmpdir = create_test_state(state, "TEST-TASK-002")
    result = detect_doom_loop("TEST-TASK-002", base_dir=tmpdir)

    assert result.is_stuck, "Should detect identical responses"
    assert result.pattern == "identical_response"
    assert "gemini" in result.suggested_action
    print("✓ test_identical_responses passed")


def test_stalled_progress():
    """Test detection of stalled progress over multiple rounds"""
    state = {
        "task_id": "TEST-TASK-003",
        "status": "running",
        "failures": [],
        "rounds": [
            {
                "round_number": 1,
                "status": "failed",
                "consensus_check": {"all_responded": False}
            },
            {
                "round_number": 2,
                "status": "failed",
                "consensus_check": {"all_responded": False}
            },
            {
                "round_number": 3,
                "status": "running",
                "consensus_check": {"all_responded": False}
            }
        ]
    }

    tmpdir = create_test_state(state, "TEST-TASK-003")
    result = detect_doom_loop("TEST-TASK-003", base_dir=tmpdir)

    assert result.is_stuck, "Should detect stalled progress"
    assert result.pattern == "stalled_progress"
    assert "Abort" in result.suggested_action or "simplify" in result.suggested_action
    print("✓ test_stalled_progress passed")


def test_healthy_discussion():
    """Test that healthy discussions are not flagged"""
    state = {
        "task_id": "TEST-TASK-004",
        "status": "running",
        "failures": [],
        "rounds": [
            {
                "round_number": 1,
                "status": "completed",
                "participants": [
                    {
                        "agent": "codex",
                        "status": "completed",
                        "parsed_response": {"decision": "Approach A"}
                    },
                    {
                        "agent": "gemini",
                        "status": "completed",
                        "parsed_response": {"decision": "Approach B"}
                    }
                ],
                "consensus_check": {"all_responded": True, "consensus_reached": False}
            }
        ]
    }

    tmpdir = create_test_state(state, "TEST-TASK-004")
    result = detect_doom_loop("TEST-TASK-004", base_dir=tmpdir)

    assert not result.is_stuck, "Should not flag healthy discussion"
    assert result.pattern == "healthy"
    print("✓ test_healthy_discussion passed")


def test_single_timeout_not_stuck():
    """Test that single timeout is not flagged as doom loop"""
    state = {
        "task_id": "TEST-TASK-005",
        "status": "running",
        "failures": [
            {"agent": "codex", "error_type": "execution_failed", "error_message": "timeout"}
        ],
        "rounds": []
    }

    tmpdir = create_test_state(state, "TEST-TASK-005")
    result = detect_doom_loop("TEST-TASK-005", base_dir=tmpdir)

    assert not result.is_stuck, "Single timeout should not trigger doom loop"
    print("✓ test_single_timeout_not_stuck passed")


if __name__ == "__main__":
    print("Running loop_detector tests...\n")

    test_repeated_timeout()
    test_identical_responses()
    test_stalled_progress()
    test_healthy_discussion()
    test_single_timeout_not_stuck()

    print("\n✅ All tests passed!")
