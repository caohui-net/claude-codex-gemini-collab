#!/usr/bin/env python3
"""
Integration helpers for auto-triggering loop detection and context compaction.

This module provides wrapper functions that collab_discuss.py can call
to automatically enhance discussions with:
- Doom loop detection
- Context compaction
"""

from pathlib import Path
from typing import Optional, Dict, Any
import sys

# Import our detection and compaction modules
try:
    from loop_detector import detect_doom_loop
    from context_compactor import compact_discussion_state
except ImportError:
    # Fallback if modules not in path
    sys.path.insert(0, str(Path(__file__).parent))
    from loop_detector import detect_doom_loop
    from context_compactor import compact_discussion_state


def check_and_handle_doom_loop(task_id: str, base_dir: str = ".") -> Optional[Dict[str, Any]]:
    """
    Check for doom loop and return detection result.

    Returns:
        Detection result dict if stuck, None if healthy
    """
    status = detect_doom_loop(task_id, base_dir)

    if status.is_stuck:
        return {
            "stuck": True,
            "pattern": status.pattern,
            "suggested_action": status.suggested_action,
            "confidence": status.confidence,
            "evidence": status.evidence
        }

    return None


def auto_compact_if_needed(task_id: str, base_dir: str = ".", min_rounds: int = 3) -> Optional[Dict[str, Any]]:
    """
    Automatically compact discussion state if rounds >= min_rounds.

    Returns:
        Compaction result dict if compacted, None if skipped
    """
    result = compact_discussion_state(task_id, base_dir)

    if not result.get("success"):
        # Not enough rounds or error
        return None

    return {
        "compacted": True,
        "savings_kb": result["savings_kb"],
        "savings_percent": result["savings_percent"],
        "rounds_compacted": result["rounds_compacted"]
    }


if __name__ == "__main__":
    # Simple test
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 discussion_enhancements.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]

    print("Checking for doom loop...")
    loop_status = check_and_handle_doom_loop(task_id)
    if loop_status:
        print(f"⚠️  Doom loop detected: {loop_status['pattern']}")
        print(f"   Suggestion: {loop_status['suggested_action']}")
    else:
        print("✅ No doom loop detected")

    print("\nAttempting compaction...")
    compact_result = auto_compact_if_needed(task_id)
    if compact_result:
        print(f"✅ Compacted: saved {compact_result['savings_kb']:.1f} KB ({compact_result['savings_percent']:.0f}%)")
    else:
        print("ℹ️  Compaction skipped (not enough rounds or already compact)")
