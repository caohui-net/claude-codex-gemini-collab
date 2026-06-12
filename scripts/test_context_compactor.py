#!/usr/bin/env python3
"""
Tests for context_compactor.py

Validates compression logic and data preservation.
"""

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from context_compactor import compact_discussion_state, _compress_round


def create_test_state(rounds_data: list, task_id: str = "TEST-COMPACT-001") -> Path:
    """Create temporary state file for testing"""
    tmpdir = Path(tempfile.mkdtemp())
    state_dir = tmpdir / ".collab" / "state"
    state_dir.mkdir(parents=True)

    state = {
        "task_id": task_id,
        "status": "running",
        "rounds": rounds_data
    }

    state_file = state_dir / f"{task_id}.json"
    with open(state_file, "w") as f:
        json.dump(state, f)

    return tmpdir


def test_compress_round():
    """Test single round compression"""
    round_data = {
        "round_number": 1,
        "status": "completed",
        "started_at": "2026-06-04T08:00:00Z",
        "completed_at": "2026-06-04T08:05:00Z",
        "participants": [
            {
                "agent": "codex",
                "status": "completed",
                "parsed_response": {
                    "consensus": True,
                    "decision": "Implement MCP adapter",
                    "reasoning": "Long reasoning text...",
                    "blocking_issues": []
                },
                "stats": {"tokens": 1500}
            }
        ],
        "consensus_check": {
            "consensus_reached": True,
            "blocking_issues": []
        }
    }

    compressed = _compress_round(round_data)

    assert compressed["round_number"] == 1
    assert compressed["status"] == "completed"
    assert compressed["consensus_reached"] == True
    assert compressed["decision"] == "Implement MCP adapter"
    assert compressed["blocking_issues"] == []
    assert compressed["_compacted"] == True

    # Verify size reduction
    original_size = len(json.dumps(round_data))
    compressed_size = len(json.dumps(compressed))
    assert compressed_size < original_size

    print("✓ test_compress_round passed")


def test_not_enough_rounds():
    """Test that compaction requires >= 3 rounds"""
    rounds = [
        {"round_number": 1, "status": "completed"},
        {"round_number": 2, "status": "completed"}
    ]

    tmpdir = create_test_state(rounds)
    result = compact_discussion_state("TEST-COMPACT-001", base_dir=tmpdir)

    assert result["success"] == False
    assert "Not enough rounds" in result["error"]

    print("✓ test_not_enough_rounds passed")


def test_compaction_preserves_recent():
    """Test that last 2 rounds are kept in full detail"""
    rounds = [
        {
            "round_number": 1,
            "status": "completed",
            "participants": [{"agent": "codex", "large_data": "x" * 1000}],
            "consensus_check": {"consensus_reached": True, "blocking_issues": []}
        },
        {
            "round_number": 2,
            "status": "completed",
            "participants": [{"agent": "gemini", "large_data": "y" * 1000}],
            "consensus_check": {"consensus_reached": False, "blocking_issues": ["Issue A"]}
        },
        {
            "round_number": 3,
            "status": "completed",
            "participants": [{"agent": "codex", "large_data": "z" * 1000}],
            "consensus_check": {"consensus_reached": True, "blocking_issues": []}
        }
    ]

    tmpdir = create_test_state(rounds)
    result = compact_discussion_state("TEST-COMPACT-001", base_dir=tmpdir)

    assert result["success"] == True
    assert result["rounds_compacted"] == 1  # Only round 1
    assert result["rounds_kept_full"] == 2   # Rounds 2, 3

    # Verify state file
    state_file = tmpdir / ".collab" / "state" / "TEST-COMPACT-001.json"
    with open(state_file) as f:
        compacted_state = json.load(f)

    # Round 1 should be compacted
    assert compacted_state["rounds"][0]["_compacted"] == True
    assert "participants" not in compacted_state["rounds"][0]

    # Rounds 2 and 3 should be full
    assert compacted_state["rounds"][1]["participants"][0]["large_data"] == "y" * 1000
    assert compacted_state["rounds"][2]["participants"][0]["large_data"] == "z" * 1000

    print("✓ test_compaction_preserves_recent passed")


def test_compaction_savings():
    """Test that compaction actually reduces file size"""
    rounds = []
    for i in range(1, 6):  # 5 rounds
        rounds.append({
            "round_number": i,
            "status": "completed",
            "participants": [
                {
                    "agent": "codex",
                    "status": "completed",
                    "response_file": f"/long/path/to/response-{i}.md",
                    "parsed_response": {
                        "consensus": True,
                        "decision": f"Decision {i}",
                        "reasoning": "Long reasoning " * 100,  # Lots of data
                        "blocking_issues": []
                    },
                    "stats": {"tokens": 5000, "latency": 1234}
                }
            ],
            "consensus_check": {"consensus_reached": True, "blocking_issues": []}
        })

    tmpdir = create_test_state(rounds, "TEST-COMPACT-002")
    result = compact_discussion_state("TEST-COMPACT-002", base_dir=tmpdir)

    assert result["success"] == True
    assert result["savings_kb"] > 0
    assert result["savings_percent"] > 0
    assert result["rounds_compacted"] == 3  # Rounds 1-3
    assert result["rounds_kept_full"] == 2   # Rounds 4-5

    print(f"✓ test_compaction_savings passed (saved {result['savings_percent']:.0f}%)")


if __name__ == "__main__":
    print("Running context_compactor tests...\n")

    test_compress_round()
    test_not_enough_rounds()
    test_compaction_preserves_recent()
    test_compaction_savings()

    print("\n✅ All context compactor tests passed!")
