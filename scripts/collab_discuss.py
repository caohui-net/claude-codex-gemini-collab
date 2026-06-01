#!/usr/bin/env python3
"""Discussion orchestration for Claude-Codex-Gemini collaboration."""

import argparse
import json
import sys
import time
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

You are {agent}. Respond with structured JSON wrapped in markers:

[RESPONSE_START]
{{
  "consensus": true/false,
  "decision": "your position or agreed decision",
  "blocking_issues": ["issue1", "issue2"] or [],
  "reasoning": "why you agree/disagree"
}}
[RESPONSE_END]

IMPORTANT: Your response MUST be wrapped between [RESPONSE_START] and [RESPONSE_END] markers.
Output ONLY the markers and JSON, nothing else.

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


def parse_discussion_artifacts(base_dir: Path, task_id: str) -> List[Dict]:
    """Parse discussion artifacts for a task."""
    artifacts_dir = base_dir / ".omc" / "collaboration" / "artifacts"
    if not artifacts_dir.exists():
        return []

    pattern = f"{task_id}-discuss-r*.md"
    artifact_files = sorted(artifacts_dir.glob(pattern))

    results = []
    for artifact_file in artifact_files:
        # Extract round and agent from filename
        # Format: TASK-ID-discuss-rN-agent-timestamp.md
        parts = artifact_file.stem.split("-")
        round_idx = next((i for i, p in enumerate(parts) if p.startswith("r") and p[1:].isdigit()), None)
        if round_idx is None:
            continue

        round_num = int(parts[round_idx][1:])
        agent = parts[round_idx + 1] if round_idx + 1 < len(parts) else "unknown"

        # Parse JSON content
        try:
            content = json.loads(artifact_file.read_text())
            results.append({
                "round": round_num,
                "agent": agent,
                "consensus": content.get("consensus", False),
                "decision": content.get("decision", ""),
                "reasoning": content.get("reasoning", ""),
                "blocking_issues": content.get("blocking_issues", [])
            })
        except json.JSONDecodeError:
            continue

    return results


def format_history_text(history: List[Dict], summary: bool = False) -> str:
    """Format discussion history as text."""
    if not history:
        return "No discussion history found."

    output = []
    for item in history:
        round_num = item["round"]
        agent = item["agent"].capitalize()
        consensus = "✓" if item["consensus"] else "✗"
        decision = item["decision"]

        if summary:
            output.append(f"[Round {round_num}] {agent}: {consensus} - {decision[:80]}...")
        else:
            output.append(f"[Round {round_num}] {agent} ({consensus})")
            output.append(f"  Decision: {decision}")
            if item["reasoning"]:
                output.append(f"  Reasoning: {item['reasoning']}")
            if item["blocking_issues"]:
                output.append(f"  Blocking: {', '.join(item['blocking_issues'])}")
            output.append("")

    return "\n".join(output)


def run_history(base_dir: Path, task_id: str, format_type: str = "text", summary: bool = False) -> int:
    """Show discussion history for a task."""
    history = parse_discussion_artifacts(base_dir, task_id)

    if format_type == "json":
        print(json.dumps(history, indent=2))
    else:
        print(format_history_text(history, summary))

    return 0


def run_discussion(
    base_dir: Path,
    task_id: str,
    topic: str,
    participants: List[str],
    max_rounds: int = 3,
    timeout_sec: int = 180
) -> int:
    """Run multi-round discussion until consensus or max rounds."""
    discussion_start = time.time()
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
    timing_log = []

    for round_num in range(1, max_rounds + 1):
        round_start = time.time()
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
            agent_start = time.time()

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

            agent_elapsed = time.time() - agent_start
            timing_log.append({
                "round": round_num,
                "agent": agent,
                "elapsed_sec": agent_elapsed,
                "cli_elapsed_sec": reply.elapsed_sec
            })

            if reply.exit_code != 0:
                print(f"❌ {agent.capitalize()} failed: {reply.parsed.get('error', 'unknown')}")
                continue

            # Verify protocol compliance: response must use markers
            if "[RESPONSE_START]" not in reply.raw_text or "[RESPONSE_END]" not in reply.raw_text:
                print(f"⚠️  {agent.capitalize()} violated output protocol (missing markers)")
                print(f"   Raw response: {reply.raw_text[:200]}...")
                print(f"   Skipping this response")
                continue

            # Save artifact
            artifact_path = save_artifact(base_dir, task_id, round_num, agent, reply.raw_text)
            artifacts_refs.append(artifact_path)

            # Extract summary from parsed response
            if isinstance(reply.parsed, dict):
                summary = reply.parsed.get("decision", "")
                if not summary:
                    summary = reply.raw_text[:100]
            else:
                summary = reply.raw_text[:100]

            # Append discussion message event
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

        round_elapsed = time.time() - round_start
        timing_log.append({
            "round": round_num,
            "type": "round_total",
            "elapsed_sec": round_elapsed
        })

        if consensus:
            discussion_elapsed = time.time() - discussion_start
            print(f"\n✅ Consensus reached in round {round_num}!")
            print(f"📁 Artifacts: {', '.join(artifacts_refs)}")
            print(f"\n⏱️  Performance Summary:")
            print(f"  Total: {discussion_elapsed:.1f}s")
            for entry in timing_log:
                if entry.get("type") == "round_total":
                    print(f"  Round {entry['round']}: {entry['elapsed_sec']:.1f}s")
                elif "agent" in entry:
                    print(f"    {entry['agent']}: {entry['elapsed_sec']:.1f}s (CLI: {entry['cli_elapsed_sec']:.1f}s)")
            return 0

        if blocking:
            print(f"⚠️  Blocking issues: {', '.join(blocking)}")

        print()

    discussion_elapsed = time.time() - discussion_start
    print(f"⚠️  No consensus after {max_rounds} rounds")
    print(f"📁 Artifacts: {', '.join(artifacts_refs)}")
    print(f"💡 Use: collab discuss conclude {task_id} \"<decision>\"")
    print(f"\n⏱️  Performance Summary:")
    print(f"  Total: {discussion_elapsed:.1f}s")
    for entry in timing_log:
        if entry.get("type") == "round_total":
            print(f"  Round {entry['round']}: {entry['elapsed_sec']:.1f}s")
        elif "agent" in entry:
            print(f"    {entry['agent']}: {entry['elapsed_sec']:.1f}s (CLI: {entry['cli_elapsed_sec']:.1f}s)")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-agent discussion orchestration")
    add_base_dir_arg(parser)
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Discuss subcommand (default behavior)
    discuss_parser = subparsers.add_parser("discuss", help="Start a discussion")
    discuss_parser.add_argument("task_id", help="Task ID")
    discuss_parser.add_argument("topic", help="Discussion topic")
    discuss_parser.add_argument("--participants", default="codex,gemini", help="Comma-separated participants")
    discuss_parser.add_argument("--max-rounds", type=int, default=3, help="Maximum discussion rounds")
    discuss_parser.add_argument("--timeout-sec", type=int, default=180, help="Timeout per agent (seconds)")

    # History subcommand
    history_parser = subparsers.add_parser("history", help="Show discussion history")
    history_parser.add_argument("task_id", help="Task ID")
    history_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    history_parser.add_argument("--summary", action="store_true", help="Show summary only")

    args = parser.parse_args()

    # Handle legacy usage (no subcommand)
    if args.command is None:
        if len(sys.argv) >= 3:
            # Legacy: collab_discuss.py TASK-ID "topic"
            args.command = "discuss"
            args.task_id = sys.argv[1]
            args.topic = sys.argv[2]
            args.participants = "codex,gemini"
            args.max_rounds = 3
            args.timeout_sec = 180
        else:
            parser.print_help()
            sys.exit(1)

    try:
        base = resolve_existing_base_dir(args.base_dir)

        if args.command == "history":
            sys.exit(run_history(base, args.task_id, args.format, args.summary))
        elif args.command == "discuss":
            participants = [p.strip() for p in args.participants.split(",")]
            sys.exit(run_discussion(base, args.task_id, args.topic, participants, args.max_rounds, args.timeout_sec))
        else:
            parser.print_help()
            sys.exit(1)

    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
