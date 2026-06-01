#!/usr/bin/env python3
"""Discussion orchestration for Claude-Codex-Gemini collaboration."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from agent_cli import run_codex, run_gemini, AgentReply
from collab_event import append_event, read_events, read_state
from collab_paths import resolve_existing_base_dir, add_base_dir_arg


def compress_history(events: List[Dict], task_id: str, max_recent: int = 2) -> str:
    """Compress discussion history: summary + recent rounds."""
    discussion_events = [
        e for e in events
        if e.get("task_id") == task_id
        and e.get("type") in ("discussion_message", "discussion_round_start", "discussion_round_end")
    ]

    if not discussion_events:
        return ""

    # Summary of early rounds
    if len(discussion_events) > max_recent:
        early_count = len(discussion_events) - max_recent
        summary = f"[Earlier: {early_count} discussion events]\n\n"
    else:
        summary = ""

    # Recent rounds (full detail)
    recent = discussion_events[-max_recent:] if len(discussion_events) > max_recent else discussion_events
    for event in recent:
        agent = event.get("agent", "unknown")
        summary_text = event.get("summary", "")
        summary += f"[{agent}]: {summary_text}\n"

    return summary.strip()


def build_discussion_prompt(
    topic: str,
    task_id: str,
    agent: str,
    round_num: int,
    history: str,
    artifacts: List[str]
) -> str:
    """Build discussion prompt with context."""
    prompt = f"""TASK-{task_id} Discussion Round {round_num}

Topic: {topic}

You are {agent}. Respond with structured JSON:
{{
  "consensus": true/false,
  "decision": "your position or agreed decision",
  "blocking_issues": ["issue1", "issue2"] or [],
  "reasoning": "why you agree/disagree"
}}

"""

    if history:
        prompt += f"Previous discussion:\n{history}\n\n"

    if artifacts:
        prompt += f"Referenced artifacts:\n"
        for art in artifacts:
            prompt += f"- {art}\n"
        prompt += "\n"

    prompt += "Respond with JSON only."
    return prompt


def judge_consensus(replies: List[AgentReply]) -> tuple[bool, List[str]]:
    """Judge if consensus reached from agent replies."""
    all_agree = True
    blocking_issues = []

    for reply in replies:
        parsed = reply.parsed
        if isinstance(parsed, dict):
            consensus = parsed.get("consensus", False)
            issues = parsed.get("blocking_issues", [])

            if not consensus:
                all_agree = False

            if isinstance(issues, list):
                blocking_issues.extend(issues)

    return all_agree, blocking_issues


def save_artifact(base_dir: Path, task_id: str, round_num: int, agent: str, content: str) -> str:
    """Save discussion artifact to file."""
    artifacts_dir = base_dir / ".omc" / "collaboration" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{task_id}-discuss-r{round_num}-{agent}-{timestamp}.md"
    artifact_path = artifacts_dir / filename

    artifact_path.write_text(content)
    return str(artifact_path.relative_to(base_dir))


def run_discussion(
    base_dir: Path,
    task_id: str,
    topic: str,
    participants: List[str],
    max_rounds: int = 3,
    timeout_sec: int = 180
) -> int:
    """Run multi-round discussion until consensus or max rounds."""
    collab_dir = base_dir / ".omc" / "collaboration"

    if not collab_dir.exists():
        print("❌ Collaboration not initialized")
        return 1

    # Read current state
    events = read_events(collab_dir / "events.jsonl")
    state = read_state(collab_dir / "state.json")

    print(f"🛠️  [Skill: Collab] Starting discussion for {task_id}")
    print(f"💬 Topic: {topic}")
    print(f"👥 Participants: {', '.join(participants)}")
    print()

    artifacts_refs = []

    for round_num in range(1, max_rounds + 1):
        print(f"⏳ [Round {round_num}] Starting...")

        # Append round start event
        append_event(
            base_dir,
            "discussion_round_start",
            "claude",
            task_id,
            f"Round {round_num} started",
            details={"round": round_num, "topic": topic}
        )

        # Refresh events after round start
        events = read_events(collab_dir / "events.jsonl")
        history = compress_history(events, task_id)

        replies = []

        # Collect responses from participants
        for agent in participants:
            if agent == "claude":
                continue  # Claude is orchestrator, not participant in this MVP

            print(f"⏳ [{agent.capitalize()}] analyzing...")

            prompt = build_discussion_prompt(
                topic, task_id, agent, round_num, history, artifacts_refs
            )

            if agent == "codex":
                reply = run_codex(prompt, base_dir, timeout_sec)
            elif agent == "gemini":
                reply = run_gemini(prompt, base_dir, timeout_sec)
            else:
                print(f"❌ Unknown agent: {agent}")
                continue

            if reply.exit_code != 0:
                print(f"❌ {agent.capitalize()} failed: {reply.parsed.get('error', 'unknown')}")
                continue

            # Save artifact
            artifact_path = save_artifact(base_dir, task_id, round_num, agent, reply.raw_text)
            artifacts_refs.append(artifact_path)

            # Append discussion message event
            summary = reply.parsed.get("decision", reply.raw_text[:100]) if isinstance(reply.parsed, dict) else reply.raw_text[:100]
            append_event(
                base_dir,
                "discussion_message",
                agent,
                task_id,
                summary,
                artifacts=[artifact_path],
                details=reply.parsed if isinstance(reply.parsed, dict) else {}
            )

            print(f"🗣️  {agent.capitalize()}: {summary}")
            print(f"   (details: {artifact_path})")

            replies.append(reply)

        # Judge consensus
        consensus, blocking = judge_consensus(replies)

        # Append round end event
        append_event(
            base_dir,
            "discussion_round_end",
            "claude",
            task_id,
            f"Round {round_num} ended",
            details={"round": round_num, "consensus": consensus, "blocking_issues": blocking}
        )

        if consensus:
            print(f"\n✅ Consensus reached in round {round_num}!")
            print(f"📁 Artifacts: {', '.join(artifacts_refs)}")
            return 0

        if blocking:
            print(f"⚠️  Blocking issues: {', '.join(blocking)}")

        print()

    print(f"⚠️  No consensus after {max_rounds} rounds")
    print(f"📁 Artifacts: {', '.join(artifacts_refs)}")
    print(f"💡 Use: collab discuss conclude {task_id} \"<decision>\"")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-agent discussion orchestration")
    add_base_dir_arg(parser)
    parser.add_argument("task_id", help="Task ID")
    parser.add_argument("topic", help="Discussion topic")
    parser.add_argument("--participants", default="codex,gemini", help="Comma-separated participants")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum discussion rounds")
    parser.add_argument("--timeout-sec", type=int, default=180, help="Timeout per agent (seconds)")
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        participants = [p.strip() for p in args.participants.split(",")]
        sys.exit(run_discussion(base, args.task_id, args.topic, participants, args.max_rounds, args.timeout_sec))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
