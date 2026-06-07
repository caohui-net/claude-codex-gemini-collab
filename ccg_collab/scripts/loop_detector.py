#!/usr/bin/env python3
"""
Doom Loop Detector for CCG Discussion System

Detects when agents are stuck in repetitive failure or response patterns.
Inspired by PraisonAI's doom loop detection mechanism.

Usage:
    from loop_detector import detect_doom_loop, LoopStatus

    status = detect_doom_loop(task_id)
    if status.is_stuck:
        print(f"Doom loop detected: {status.pattern}")
        print(f"Suggested action: {status.suggested_action}")
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import defaultdict


@dataclass
class LoopStatus:
    """Result of doom loop detection"""
    is_stuck: bool
    pattern: Optional[str] = None
    suggested_action: Optional[str] = None
    confidence: float = 0.0
    evidence: List[str] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


def detect_doom_loop(task_id: str, base_dir: str = ".") -> LoopStatus:
    """
    Detect if a discussion task is stuck in a doom loop.

    Args:
        task_id: Discussion task ID
        base_dir: Workspace root directory

    Returns:
        LoopStatus indicating if stuck and suggested recovery
    """
    state_file = Path(base_dir) / ".omc" / "collaboration" / "state" / f"{task_id}.json"

    if not state_file.exists():
        return LoopStatus(is_stuck=False, pattern="no_state_file")

    with open(state_file) as f:
        state = json.load(f)

    # Check 1: Repeated timeouts
    timeout_pattern = _check_timeout_pattern(state)
    if timeout_pattern.is_stuck:
        return timeout_pattern

    # Check 2: Identical responses
    identical_pattern = _check_identical_responses(state)
    if identical_pattern.is_stuck:
        return identical_pattern

    # Check 3: No progress over rounds
    stalled_pattern = _check_stalled_progress(state)
    if stalled_pattern.is_stuck:
        return stalled_pattern

    return LoopStatus(is_stuck=False, pattern="healthy")


def _check_timeout_pattern(state: Dict[str, Any]) -> LoopStatus:
    """Check for repeated timeout failures"""
    failures = state.get("failures", [])

    if len(failures) < 2:
        return LoopStatus(is_stuck=False)

    # Count timeouts per agent
    timeout_counts = defaultdict(int)
    for failure in failures:
        if failure.get("error_type") == "execution_failed" and "timeout" in failure.get("error_message", ""):
            agent = failure.get("agent")
            timeout_counts[agent] += 1

    # Doom loop if same agent times out 2+ times
    for agent, count in timeout_counts.items():
        if count >= 2:
            return LoopStatus(
                is_stuck=True,
                pattern="repeated_timeout",
                suggested_action=f"Skip {agent} or increase timeout",
                confidence=0.9,
                evidence=[f"{agent} timed out {count} times"]
            )

    return LoopStatus(is_stuck=False)


def _check_identical_responses(state: Dict[str, Any]) -> LoopStatus:
    """Check for identical responses across rounds"""
    rounds = state.get("rounds", [])

    if len(rounds) < 2:
        return LoopStatus(is_stuck=False)

    # Extract decisions from each round
    decisions_by_agent = defaultdict(list)

    for round_data in rounds:
        if round_data.get("status") != "completed":
            continue

        for participant in round_data.get("participants", []):
            if participant.get("status") != "completed":
                continue

            agent = participant.get("agent")
            parsed = participant.get("parsed_response", {})
            decision = parsed.get("decision") if isinstance(parsed, dict) else None

            if decision:
                decisions_by_agent[agent].append(decision)

    # Check for identical consecutive decisions
    for agent, decisions in decisions_by_agent.items():
        if len(decisions) >= 2:
            if decisions[-1] == decisions[-2]:
                return LoopStatus(
                    is_stuck=True,
                    pattern="identical_response",
                    suggested_action=f"Prompt {agent} with new context or skip",
                    confidence=0.8,
                    evidence=[f"{agent} gave identical response in last 2 rounds"]
                )

    return LoopStatus(is_stuck=False)


def _check_stalled_progress(state: Dict[str, Any]) -> LoopStatus:
    """Check if discussion is stalled without progress"""
    rounds = state.get("rounds", [])

    if len(rounds) < 3:
        return LoopStatus(is_stuck=False)

    # Check last 3 rounds
    recent_rounds = rounds[-3:]

    # Count failures in recent rounds
    failure_count = 0
    for round_data in recent_rounds:
        if round_data.get("status") != "completed":
            failure_count += 1
            continue

        consensus_check = round_data.get("consensus_check", {})
        if not consensus_check.get("all_responded", False):
            failure_count += 1

    # Doom loop if 3 consecutive rounds without progress
    if failure_count >= 3:
        return LoopStatus(
            is_stuck=True,
            pattern="stalled_progress",
            suggested_action="Abort discussion or simplify topic",
            confidence=0.95,
            evidence=[f"{failure_count}/3 recent rounds failed to complete"]
        )

    return LoopStatus(is_stuck=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 loop_detector.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    status = detect_doom_loop(task_id)

    print(f"Task: {task_id}")
    print(f"Stuck: {status.is_stuck}")
    print(f"Pattern: {status.pattern}")

    if status.is_stuck:
        print(f"Confidence: {status.confidence:.0%}")
        print(f"Suggested action: {status.suggested_action}")
        print(f"Evidence: {', '.join(status.evidence)}")
