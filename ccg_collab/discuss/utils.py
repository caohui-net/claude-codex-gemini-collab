"""Discussion utility functions."""

from pathlib import Path
from typing import List, Dict, Optional


def compress_history(events: List[Dict], task_id: str, max_recent: int = 2) -> str:
    """Compress discussion history: summary + recent rounds."""
    discussion_events = [
        e for e in events
        if e.get("task_id") == task_id
        and e.get("type") in ("discussion_message", "discussion_round_start", "discussion_round_end")
    ]

    if not discussion_events:
        return ""

    if len(discussion_events) > max_recent:
        early_count = len(discussion_events) - max_recent
        summary = f"[Earlier: {early_count} discussion events]\n\n"
    else:
        summary = ""

    recent = discussion_events[-max_recent:] if len(discussion_events) > max_recent else discussion_events
    for event in recent:
        agent = event.get("agent", "unknown")
        summary_text = event.get("summary", "")
        summary += f"[{agent}]: {summary_text}\n"

    return summary.strip()


def format_history_text(history: List[Dict], summary: bool = False) -> str:
    """Format history as readable text."""
    if not history:
        return ""

    lines = []
    for item in history:
        agent = item.get("agent", "unknown")
        text = item.get("summary", "") if summary else item.get("content", "")
        lines.append(f"[{agent}]: {text}")

    return "\n".join(lines)
