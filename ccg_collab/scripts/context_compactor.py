#!/usr/bin/env python3
"""
Context Compactor for CCG Discussion System

Compresses old discussion rounds to reduce state file size and token usage.
Inspired by PraisonAI's context compaction mechanism.

Usage:
    from context_compactor import compact_discussion_state

    result = compact_discussion_state(task_id)
    print(f"Saved {result['savings_kb']:.1f} KB")
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def compact_discussion_state(task_id: str, base_dir: str = ".") -> Dict[str, Any]:
    """
    Compact discussion state by compressing old rounds.

    Strategy:
    - Keep rounds N-1 and N (last 2) in full detail
    - Compress rounds 1..N-2 to essentials (decision + consensus)
    - Preserve all blocking issues

    Args:
        task_id: Discussion task ID
        base_dir: Workspace root

    Returns:
        Dictionary with:
        - success: bool
        - original_size: bytes
        - compacted_size: bytes
        - savings_kb: float
        - rounds_compacted: int
    """
    state_file = Path(base_dir) / ".collab" / "state" / f"{task_id}.json"

    if not state_file.exists():
        return {"success": False, "error": "State file not found"}

    # Load original state
    with open(state_file) as f:
        original_content = f.read()
        state = json.loads(original_content)

    original_size = len(original_content.encode())

    # Check if compaction needed
    rounds = state.get("rounds", [])
    if len(rounds) < 3:
        return {
            "success": False,
            "error": "Not enough rounds (need >= 3)",
            "rounds": len(rounds)
        }

    # Compact old rounds (1..N-2)
    compacted_rounds = []
    rounds_to_compress = rounds[:-2]  # All except last 2
    rounds_to_keep = rounds[-2:]      # Last 2 rounds full

    for round_data in rounds_to_compress:
        compacted_rounds.append(_compress_round(round_data))

    # Combine: compacted old + full recent
    state["rounds"] = compacted_rounds + rounds_to_keep

    # Write compacted state
    compacted_content = json.dumps(state, indent=2, ensure_ascii=False)
    with open(state_file, "w") as f:
        f.write(compacted_content)

    compacted_size = len(compacted_content.encode())
    savings = original_size - compacted_size

    return {
        "success": True,
        "original_size": original_size,
        "compacted_size": compacted_size,
        "savings_kb": savings / 1024,
        "savings_percent": (savings / original_size * 100) if original_size > 0 else 0,
        "rounds_compacted": len(rounds_to_compress),
        "rounds_kept_full": len(rounds_to_keep)
    }


def _compress_round(round_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compress single round to essentials"""
    consensus_check = round_data.get("consensus_check", {})

    # Extract decision from successful participants
    decision = _extract_decision(round_data)

    return {
        "round_number": round_data.get("round_number"),
        "status": round_data.get("status"),
        "consensus_reached": consensus_check.get("consensus_reached"),
        "decision": decision,
        "blocking_issues": consensus_check.get("blocking_issues", []),
        "_compacted": True  # Marker for debugging
    }


def _extract_decision(round_data: Dict[str, Any]) -> Optional[str]:
    """Extract consensus decision from round participants"""
    participants = round_data.get("participants", [])

    # Try to find a participant with consensus=true
    for participant in participants:
        if participant.get("status") != "completed":
            continue

        parsed = participant.get("parsed_response")
        if not isinstance(parsed, dict):
            continue

        if parsed.get("consensus"):
            return parsed.get("decision")

    # Fallback: return first available decision
    for participant in participants:
        if participant.get("status") == "completed":
            parsed = participant.get("parsed_response")
            if isinstance(parsed, dict) and parsed.get("decision"):
                return parsed.get("decision")

    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 context_compactor.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    result = compact_discussion_state(task_id)

    if result["success"]:
        print(f"✅ Compaction successful")
        print(f"   Original: {result['original_size'] / 1024:.1f} KB")
        print(f"   Compacted: {result['compacted_size'] / 1024:.1f} KB")
        print(f"   Savings: {result['savings_kb']:.1f} KB ({result['savings_percent']:.0f}%)")
        print(f"   Rounds compacted: {result['rounds_compacted']}")
        print(f"   Rounds kept full: {result['rounds_kept_full']}")
    else:
        print(f"❌ Compaction failed: {result.get('error')}")
        sys.exit(1)
