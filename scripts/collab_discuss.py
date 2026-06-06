#!/usr/bin/env python3
"""Discussion orchestration for Claude-Codex-Gemini collaboration."""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from agent_cli import run_codex, run_gemini, AgentReply
from collab_event import append_event, read_events, read_state
from collab_init import init_collaboration
from collab_paths import resolve_existing_base_dir, add_base_dir_arg
from discussion_enhancements import check_and_handle_doom_loop, auto_compact_if_needed
from rmux_utils import check_rmux_available, get_tmux_info
from collab_state import (
    init_task_state, load_task_state, save_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round, get_pending_participants, get_task_state_file
)


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


def save_discussion_context(
    base_dir: Path,
    task_id: str,
    round_num: int,
    topic: str,
    history: str,
    artifacts: List[str]
) -> str:
    """Save discussion context to file, return relative path."""
    context_dir = base_dir / ".omc" / "collaboration" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{task_id}-r{round_num}-context.md"
    context_path = context_dir / filename

    content = f"""# Discussion Context

**Task:** {task_id}
**Round:** {round_num}

## Topic

{topic}

"""

    if history:
        content += f"""## Previous Discussion

{history}

"""

    if artifacts:
        content += "## Referenced Artifacts\n\n"
        for art in artifacts:
            content += f"- {art}\n"
        content += "\n"

    context_path.write_text(content, encoding="utf-8")
    return str(context_path.relative_to(base_dir))


def build_discussion_prompt(
    topic: str,
    task_id: str,
    agent: str,
    round_num: int,
    history: str,
    artifacts: List[str],
    context_file: Optional[str] = None
) -> str:
    """Build discussion prompt with context (file reference or inline)."""

    # File reference mode (token-optimized)
    if context_file:
        prompt = f"""TASK-{task_id} Discussion Round {round_num}

You are {agent}. Read the discussion context from: {context_file}

Respond with structured JSON wrapped in markers:

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
        return prompt

    # Inline mode (backward compatible)
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


def save_consensus_contract(base_dir: Path, task_id: str, task_state: dict):
    """Save consensus.json contract for execution phase.

    Only called when consensus is reached.
    """
    if not task_state.get('final_consensus', {}).get('reached'):
        return

    consensus = {
        "task_id": task_id,
        "achieved_at": datetime.now(timezone.utc).isoformat(),
        "decision": task_state['final_consensus']['decision'],
        "round": task_state['final_consensus'].get('round'),
        "tasks": [],  # Minimal implementation - can be parsed later
        "blocking_issues": []
    }

    output_path = base_dir / ".omc/collaboration/tasks" / task_id / "consensus.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(consensus, f, indent=2, ensure_ascii=False)


def judge_consensus(replies: List[AgentReply]) -> tuple[bool, List[str]]:
    """Judge if consensus reached from agent replies."""
    # No replies means no consensus
    if not replies:
        return False, []

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

        # Parse JSON content (handle marker-wrapped format)
        try:
            raw_content = artifact_file.read_text()

            # Extract JSON between [RESPONSE_START] and [RESPONSE_END] markers
            start_marker = "[RESPONSE_START]"
            end_marker = "[RESPONSE_END]"

            if start_marker in raw_content and end_marker in raw_content:
                start_idx = raw_content.index(start_marker) + len(start_marker)
                end_idx = raw_content.index(end_marker)
                json_content = raw_content[start_idx:end_idx].strip()
            else:
                # Fallback: try parsing entire content
                json_content = raw_content

            content = json.loads(json_content)
            results.append({
                "round": round_num,
                "agent": agent,
                "consensus": content.get("consensus", False),
                "decision": content.get("decision", ""),
                "reasoning": content.get("reasoning", ""),
                "blocking_issues": content.get("blocking_issues", [])
            })
        except (json.JSONDecodeError, ValueError):
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


def run_scan(base_dir: Path) -> int:
    """Scan for incomplete discussion tasks."""
    state_dir = base_dir / ".omc" / "collaboration" / "state"

    if not state_dir.exists():
        print("📂 No state directory found")
        return 0

    state_files = list(state_dir.glob("*.json"))

    if not state_files:
        print("✓ No discussion tasks found")
        return 0

    incomplete_tasks = []
    pending_tasks = []
    corrupted_tasks = []

    for state_file in state_files:
        task_id = state_file.stem

        try:
            task_state = load_task_state(base_dir, task_id)

            if task_state is None:
                # Corrupted JSON
                corrupted_tasks.append({"task_id": task_id, "file": str(state_file)})
                continue

            # Check required fields
            status = task_state.get("status")
            if status is None:
                corrupted_tasks.append({"task_id": task_id, "error": "missing status field"})
                continue

            # Categorize by status
            if status in ("running", "failed"):
                incomplete_tasks.append({
                    "task_id": task_state["task_id"],
                    "status": status,
                    "topic": task_state.get("topic", "N/A"),
                    "rounds": len(task_state.get("rounds", [])),
                    "created": task_state.get("created_at", "N/A")
                })
            elif status == "pending":
                pending_tasks.append({
                    "task_id": task_state["task_id"],
                    "topic": task_state.get("topic", "N/A"),
                    "created": task_state.get("created_at", "N/A")
                })

        except KeyError as e:
            corrupted_tasks.append({"task_id": task_id, "error": f"missing field: {e}"})
        except Exception as e:
            corrupted_tasks.append({"task_id": task_id, "error": str(e)})

    # Report results
    total_issues = len(incomplete_tasks) + len(pending_tasks) + len(corrupted_tasks)

    if total_issues == 0:
        print("✓ No incomplete tasks found")
        return 0

    if incomplete_tasks:
        print(f"⚠️  Found {len(incomplete_tasks)} incomplete task(s):\n")
        for task in incomplete_tasks:
            print(f"📋 {task['task_id']}")
            print(f"   Status: {task['status']}")
            print(f"   Topic: {task['topic']}")
            print(f"   Rounds: {task['rounds']}")
            print(f"   Created: {task['created']}")
            print(f"   Resume: python3 scripts/collab_discuss.py resume {task['task_id']}")
            print()

    if pending_tasks:
        print(f"⏸️  Found {len(pending_tasks)} pending task(s):\n")
        for task in pending_tasks:
            print(f"📋 {task['task_id']}")
            print(f"   Topic: {task['topic']}")
            print(f"   Created: {task['created']}")
            print()

    if corrupted_tasks:
        print(f"❌ Found {len(corrupted_tasks)} corrupted task(s):\n")
        for task in corrupted_tasks:
            print(f"📋 {task['task_id']}")
            if "file" in task:
                print(f"   File: {task['file']}")
            if "error" in task:
                print(f"   Error: {task['error']}")
            print()

    return 0


def run_status(base_dir: Path, task_id: str) -> int:
    """Show task status."""
    task_state = load_task_state(base_dir, task_id)
    if task_state is None:
        print(f"❌ No state found for {task_id}")
        return 1

    print(f"📊 Task Status: {task_id}")
    print(f"   Status: {task_state['status']}")
    print(f"   Topic: {task_state['topic']}")
    print(f"   Created: {task_state['created_at']}")

    if task_state['status'] == 'completed':
        print(f"   Completed: {task_state['completed_at']}")
        print(f"   Consensus: {task_state['final_consensus']['reached']}")
        print(f"   Decision: {task_state['final_consensus']['decision']}")
        return 0

    # Show rounds
    print(f"\n📝 Rounds: {len(task_state['rounds'])}")
    for r in task_state['rounds']:
        print(f"   Round {r['round_number']}: {r['status']}")
        if r.get('_compacted'):
            print(f"      📦 (compacted)")
        else:
            for p in r['participants']:
                status_icon = "✓" if p['status'] == 'completed' else "✗" if p['status'] == 'failed' else "⏳"
                print(f"      {status_icon} {p['agent']}: {p['status']}")
                if p['error']:
                    print(f"         Error: {p['error']['type']} - {p['error']['message']}")

    # Show failures
    if task_state['failures']:
        print(f"\n⚠️  Failures: {len(task_state['failures'])}")
        for f in task_state['failures'][-3:]:
            print(f"   Round {f['round_number']}, {f['agent']}: {f['error_type']}")

    return 0


def run_conclude(base_dir: Path, task_id: str, decision: str) -> int:
    """Manually conclude discussion with final decision."""
    task_state = load_task_state(base_dir, task_id)
    if task_state is None:
        print(f"❌ No state found for {task_id}")
        return 1

    if task_state['status'] == 'completed' and task_state['final_consensus'].get('reached', False):
        print(f"⚠️  Task {task_id} already completed with consensus")
        return 0

    # Update final consensus
    task_state['final_consensus'] = {
        'reached': True,
        'decision': decision,
        'method': 'manual_conclude'
    }
    task_state['status'] = 'completed'
    task_state['completed_at'] = datetime.now(timezone.utc).isoformat()

    # Save state
    save_task_state(base_dir, task_id, task_state)

    # Append discussion_concluded event
    append_event(
        base_dir,
        'discussion_concluded',
        'system',
        task_id,
        decision,
        details={'method': 'manual_conclude'}
    )

    print(f"✅ Discussion concluded for {task_id}")
    print(f"📋 Decision: {decision}")
    return 0


def run_resume(base_dir: Path, task_id: str, retry_failed: bool = False) -> int:
    """Resume interrupted discussion."""
    task_state = load_task_state(base_dir, task_id)
    if task_state is None:
        print(f"❌ No state found for {task_id}")
        return 1

    status = task_state["status"]
    if status == "completed":
        print(f"✅ Task already completed")
        print(f"   Consensus: {task_state['final_consensus']['reached']}")
        print(f"   Decision: {task_state['final_consensus']['decision']}")
        return 0

    if status == "pending":
        print(f"⚠️  Task not started yet. Use 'discuss' command instead.")
        return 1

    # Resume from current round
    topic = task_state["topic"]
    participants = task_state["participants"]
    current_round = len(task_state["rounds"])

    # Read limits from state (backward compatible: default to 10 if missing)
    limits = task_state.get("limits", {"max_rounds": 10, "hard_max_rounds": 10})
    resume_max_rounds = limits.get("hard_max_rounds", 10)
    resume_hard_max_rounds = limits.get("hard_max_rounds", 10)

    print(f"🔄 Resuming {task_id} from round {current_round}")

    # Reset failed participants to pending if retry requested
    if retry_failed and current_round <= len(task_state["rounds"]):
        round_state = task_state["rounds"][current_round - 1]
        retry_count = 0
        for p in round_state["participants"]:
            if p["status"] == "failed":
                p["status"] = "pending"
                p["error"] = None
                retry_count += 1
        if retry_count > 0:
            save_task_state(base_dir, task_id, task_state)
            print(f"   Retrying {retry_count} failed participant(s)")

    # Continue discussion (use hard_max_rounds as new max to allow full continuation)
    return run_discussion(base_dir, task_id, topic, participants,
                         max_rounds=resume_max_rounds, hard_max_rounds=resume_hard_max_rounds,
                         timeout_sec=180, resume=True)


def invoke_agent_parallel(
    agent: str,
    prompt: str,
    base_dir: Path,
    timeout_sec: int,
    use_tmux: bool,
    keep_session: bool
) -> AgentReply:
    """Invoke single agent (for parallel execution)."""
    if agent == "codex":
        return run_codex(prompt, base_dir, timeout_sec, use_tmux=use_tmux, keep_session=keep_session)
    elif agent == "gemini":
        return run_gemini(prompt, base_dir, timeout_sec, use_tmux=use_tmux, keep_session=keep_session)
    else:
        return AgentReply(
            agent=agent,
            raw_text="",
            parsed={"error": f"unknown_agent_{agent}"},
            artifact_path="",
            elapsed_sec=0,
            exit_code=1
        )


def run_discussion(
    base_dir: Path,
    task_id: str,
    topic: str,
    participants: List[str],
    max_rounds: int = 3,
    hard_max_rounds: int = 10,
    timeout_sec: int = 180,
    resume: bool = False,
    mode: str = "full"
) -> int:
    """Run multi-round discussion until consensus or max rounds.

    mode: 'full' (default) - multi-round persistent, requires init
          'fast' - single-round stateless, no init required (ccg-style)
    """
    discussion_start = time.time()
    collab_dir = base_dir / ".omc" / "collaboration"

    # Fast mode: single-round stateless, no init required
    if mode == "fast":
        print("⚡ [Fast Mode] Single-round stateless discussion (ccg-style)")
        print(f"💬 Topic: {topic}")
        print(f"👥 Participants: {', '.join(participants)}")
        print()

        # Ensure fast artifacts directory
        fast_artifacts_dir = collab_dir / "artifacts" / "fast"
        fast_artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Run single round: invoke each agent
        artifacts_refs = []
        for participant in participants:
            print(f"🤖 Invoking {participant}...")
            try:
                if participant == "codex":
                    reply = run_codex(topic, base_dir, timeout_sec=timeout_sec)
                elif participant == "gemini":
                    reply = run_gemini(topic, base_dir, timeout_sec=timeout_sec)
                else:
                    print(f"⚠️  Unknown participant: {participant}")
                    continue

                if reply.artifact_path:
                    artifacts_refs.append(str(reply.artifact_path))
                    print(f"   ✓ Artifact: {reply.artifact_path}")
            except Exception as e:
                print(f"   ❌ {participant} failed: {e}")

        # Output summary
        discussion_elapsed = time.time() - discussion_start
        print(f"\n⏱️  Total: {discussion_elapsed:.1f}s")
        print(f"📁 Artifacts: {', '.join(artifacts_refs) if artifacts_refs else 'none'}")
        print("\n💡 Fast mode complete. Use full mode for multi-round consensus.")
        return 0
    elif not collab_dir.exists():
        print("❌ Collaboration not initialized. Run: collab init")
        return 1

    # Initialize or load task state
    task_state = load_task_state(base_dir, task_id)
    if task_state is None:
        task_state = init_task_state(base_dir, task_id, topic, participants, max_rounds, hard_max_rounds)
        print(f"🛠️  [Skill: Collab] Starting discussion for {task_id}")

        # Append discussion_started event
        append_event(
            base_dir,
            'discussion_started',
            'system',
            task_id,
            f"Discussion started: {topic}",
            details={'topic': topic, 'participants': participants}
        )
    else:
        print(f"🔄 [Skill: Collab] Resuming discussion for {task_id}")
        print(f"   Status: {task_state['status']}, Rounds: {len(task_state['rounds'])}")

    # Read current state
    events = read_events(collab_dir / "events.jsonl")
    state = read_state(collab_dir / "state.json")

    print(f"💬 Topic: {topic}")
    print(f"👥 Participants: {', '.join(participants)}")
    print()

    artifacts_refs = []
    timing_log = []

    # Determine starting round
    start_round_num = 1
    if resume and len(task_state["rounds"]) > 0:
        last_round = task_state["rounds"][-1]
        # If last round completed, start from next round; otherwise resume from last round
        if last_round["status"] == "completed":
            start_round_num = len(task_state["rounds"]) + 1
        else:
            start_round_num = len(task_state["rounds"])
        # Collect existing artifacts
        for artifact in task_state["artifacts"]["files"]:
            artifacts_refs.append(artifact)

    # Detect tmux availability once before discussion loop
    use_tmux_env = os.environ.get("CCG_USE_TMUX", "").lower()
    if use_tmux_env == "false":
        use_tmux = False
        tmux_status = "disabled by CCG_USE_TMUX=false"
    elif use_tmux_env == "true":
        info = get_tmux_info()
        use_tmux = info['available']
        if use_tmux:
            version_str = f" ({info['version']})" if info['version'] else ""
            tmux_status = f"enabled by CCG_USE_TMUX=true{version_str}"
        else:
            tmux_status = f"requested but unavailable (reason: {info['reason']})"
    else:
        # Not set - auto-detect
        info = get_tmux_info()
        use_tmux = info['available']
        if use_tmux:
            version_str = f" ({info['version']})" if info['version'] else ""
            tmux_status = f"auto-enabled{version_str}"
        else:
            tmux_status = f"auto-disabled (reason: {info['reason']})"

    print(f"🔧 Tmux: {tmux_status}")
    print()

    # Cap loop at hard_max_rounds to prevent exceeding hard limit
    effective_max = min(max_rounds, hard_max_rounds)
    for round_num in range(start_round_num, effective_max + 1):
        round_start = time.time()
        print(f"⏳ [Round {round_num}] Starting...")

        # Check for doom loop before proceeding
        try:
            loop_status = check_and_handle_doom_loop(task_id, str(base_dir))
            if loop_status:
                print(f"⚠️  Doom loop detected: {loop_status['pattern']}")
                print(f"   Suggested action: {loop_status['suggested_action']}")
        except Exception as e:
            print(f"⚠️  Doom loop detection failed: {e}")

        # Auto-compact if needed (rounds >= 3)
        try:
            if len(task_state["rounds"]) >= 3:
                compact_result = auto_compact_if_needed(task_id, str(base_dir))
                if compact_result:
                    print(f"📦 Compacted: saved {compact_result['savings_kb']:.1f} KB ({compact_result['savings_percent']:.0f}%)")
                    # Reload state to sync memory with disk after compaction
                    task_state = load_task_state(base_dir, task_id)
        except Exception as e:
            print(f"⚠️  Auto-compaction failed: {e}")

        # Initialize round in state (skip if already exists during resume)
        round_exists = round_num <= len(task_state["rounds"])
        if not round_exists:
            task_state = start_round(task_state, round_num, participants)
            save_task_state(base_dir, task_id, task_state)

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

        # Prepare agents to execute (exclude claude, skip already completed)
        agents_to_run = []
        for agent in participants:
            if agent == "claude":
                continue

            # Check if already completed/failed in resume case
            skip_execution = False
            if resume and round_num <= len(task_state["rounds"]):
                round_state = task_state["rounds"][round_num - 1]
                for p in round_state["participants"]:
                    if p["agent"] == agent and p["status"] in ("completed", "failed"):
                        status_label = p["status"].capitalize()
                        print(f"✓ [{agent.capitalize()}] already {status_label.lower()} (skipping)")
                        if p["status"] == "completed" and p["parsed_response"]:
                            replies.append(AgentReply(
                                agent=agent,
                                exit_code=0,
                                raw_text="",
                                parsed=p["parsed_response"],
                                artifact_path=p.get("response_file", ""),
                                elapsed_sec=0
                            ))
                        skip_execution = True
                        break

            if not skip_execution:
                agents_to_run.append(agent)

        # Prepare context (shared by all agents)
        use_file_ref = os.environ.get("CCG_USE_FILE_REF", "true").lower() == "true"
        context_file = None
        if use_file_ref:
            context_file = save_discussion_context(
                base_dir, task_id, round_num, topic, history, artifacts_refs
            )
        keep_session = os.environ.get("CCG_KEEP_SESSION", "").lower() == "true"

        # Execute agents in parallel
        if agents_to_run:
            print(f"⏳ Invoking {len(agents_to_run)} agent(s) in parallel: {', '.join(agents_to_run)}")

            with ThreadPoolExecutor(max_workers=len(agents_to_run)) as executor:
                # Submit all agents
                futures = {}
                for agent in agents_to_run:
                    # Mark as started
                    task_state = start_participant(task_state, round_num, agent)
                    save_task_state(base_dir, task_id, task_state)

                    prompt = build_discussion_prompt(
                        topic, task_id, agent, round_num, history, artifacts_refs, context_file
                    )

                    agent_start = time.time()
                    future = executor.submit(
                        invoke_agent_parallel, agent, prompt, base_dir,
                        timeout_sec, use_tmux, keep_session
                    )
                    futures[future] = (agent, agent_start)

                # Collect results as they complete
                for future in as_completed(futures):
                    agent, agent_start = futures[future]
                    agent_elapsed = time.time() - agent_start

                    try:
                        reply = future.result()
                    except Exception as e:
                        print(f"❌ [{agent.capitalize()}] exception: {e}")
                        task_state = fail_participant(task_state, round_num, agent, "exception", str(e))
                        save_task_state(base_dir, task_id, task_state)
                        continue

                    timing_log.append({
                        "round": round_num,
                        "agent": agent,
                        "elapsed_sec": agent_elapsed,
                        "cli_elapsed_sec": reply.elapsed_sec
                    })

                    if reply.exit_code != 0:
                        error_msg = str(reply.parsed.get('error', 'unknown'))
                        print(f"❌ [{agent.capitalize()}] failed: {error_msg}")
                        task_state = fail_participant(task_state, round_num, agent, "execution_failed", error_msg)
                        save_task_state(base_dir, task_id, task_state)
                        continue

                    # Verify protocol compliance
                    if "[RESPONSE_START]" not in reply.raw_text or "[RESPONSE_END]" not in reply.raw_text:
                        print(f"❌ [{agent.capitalize()}] protocol violation: missing markers")
                        task_state = fail_participant(task_state, round_num, agent, "format_error", "missing markers")
                        save_task_state(base_dir, task_id, task_state)
                        continue

                    # Save artifact
                    artifact_path = save_artifact(base_dir, task_id, round_num, agent, reply.raw_text)
                    artifacts_refs.append(artifact_path)

                    # Mark completed
                    task_state = complete_participant(task_state, round_num, agent, artifact_path,
                                                     reply.parsed if isinstance(reply.parsed, dict) else {})
                    save_task_state(base_dir, task_id, task_state)

                    # Extract summary
                    if isinstance(reply.parsed, dict):
                        summary = reply.parsed.get("decision", "")
                        if not summary:
                            summary = reply.raw_text[:100]
                    else:
                        summary = reply.raw_text[:100]

                    # Log event
                    append_event(
                        base_dir,
                        "discussion_message",
                        agent,
                        task_id,
                        summary,
                        artifacts=[artifact_path],
                        details=reply.parsed if isinstance(reply.parsed, dict) else {}
                    )

                    print(f"✓ [{agent.capitalize()}] {summary[:60]}...")
                    replies.append(reply)

        # Check if all participants successfully replied
        expected_participant_count = len([p for p in participants if p != "claude"])
        if len(replies) < expected_participant_count:
            print(f"⚠️  Not all required participants completed successfully. Consensus blocked.")
            consensus = False
            blocking = ["Not all required participants completed successfully (some failed or were skipped)."]
        else:
            # Judge consensus
            consensus, blocking = judge_consensus(replies)

        # Mark round as completed
        task_state = complete_round(task_state, round_num, consensus, blocking,
                                   actual_responded=len(replies),
                                   expected_count=expected_participant_count)
        save_task_state(base_dir, task_id, task_state)

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

            # Aggregate decisions from participant responses
            decisions = []
            for reply in replies:
                if isinstance(reply.parsed, dict):
                    decision = reply.parsed.get("decision", "")
                    if decision:
                        decisions.append(f"[{reply.agent}] {decision}")

            final_decision = "\n".join(decisions) if decisions else "Consensus reached"

            # Set terminal state for consensus
            task_state['status'] = 'completed'
            task_state['final_consensus'] = {
                'reached': True,
                'decision': final_decision,
                'round': round_num
            }
            task_state['completed_at'] = datetime.now(timezone.utc).isoformat()
            save_task_state(base_dir, task_id, task_state)

            # Save consensus contract for execution phase
            save_consensus_contract(base_dir, task_id, task_state)

            # Append discussion_concluded event
            append_event(
                base_dir,
                'discussion_concluded',
                'system',
                task_id,
                f"Consensus reached in round {round_num}",
                details={'consensus': True, 'decision': final_decision}
            )

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
    current_round = len(task_state['rounds'])

    # Check if hard limit reached
    if current_round >= hard_max_rounds:
        # Hard limit: force stop
        task_state['status'] = 'completed'
        task_state['final_consensus'] = {
            'reached': False,
            'reason': 'hard_round_limit_reached',
            'decision': ''
        }
        task_state['completed_at'] = datetime.now(timezone.utc).isoformat()
        save_task_state(base_dir, task_id, task_state)

        append_event(
            base_dir,
            'discussion_concluded',
            'system',
            task_id,
            f"Discussion stopped: hard limit ({hard_max_rounds} rounds) reached",
            details={'consensus': False, 'reason': 'hard_round_limit_reached'}
        )

        print(f"🛑 Hard limit reached: {hard_max_rounds} rounds without consensus")
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

    # Soft limit reached but not hard limit: allow manual continue
    print(f"ℹ️  Soft limit ({max_rounds} rounds) reached without consensus")
    print(f"   Discussion can continue (up to {hard_max_rounds} rounds total)")
    print(f"📁 Artifacts: {', '.join(artifacts_refs)}")
    print(f"💡 Options:")
    print(f"   - Resume: collab discuss resume {task_id}")
    print(f"   - Conclude manually: collab discuss conclude {task_id} \"<decision>\"")
    print(f"\n⏱️  Performance Summary:")
    print(f"  Total: {discussion_elapsed:.1f}s")
    for entry in timing_log:
        if entry.get("type") == "round_total":
            print(f"  Round {entry['round']}: {entry['elapsed_sec']:.1f}s")
        elif "agent" in entry:
            print(f"    {entry['agent']}: {entry['elapsed_sec']:.1f}s (CLI: {entry['cli_elapsed_sec']:.1f}s)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-agent discussion orchestration")
    add_base_dir_arg(parser)
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Discuss subcommand (default behavior)
    discuss_parser = subparsers.add_parser("discuss", help="Start a discussion")
    discuss_parser.add_argument("task_id", nargs='?', help="Task ID (optional if --topic provided)")
    discuss_parser.add_argument("topic", nargs='?', help="Discussion topic (positional, or use --topic)")
    discuss_parser.add_argument("--topic", dest="topic_flag", help="Discussion topic (alternative to positional)")
    discuss_parser.add_argument("--mode", choices=["fast", "full"], default="full", help="fast: single-round stateless (ccg-style), full: multi-round persistent (default)")
    discuss_parser.add_argument("--participants", default="codex,gemini", help="Comma-separated participants")
    discuss_parser.add_argument("--max-rounds", type=int, default=3, help="Maximum discussion rounds")
    discuss_parser.add_argument("--timeout-sec", type=int, default=180, help="Timeout per agent (seconds)")

    # History subcommand
    history_parser = subparsers.add_parser("history", help="Show discussion history")
    history_parser.add_argument("task_id", help="Task ID")
    history_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    history_parser.add_argument("--summary", action="store_true", help="Show summary only")

    # Resume subcommand
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted discussion")
    resume_parser.add_argument("task_id", help="Task ID")
    resume_parser.add_argument("--retry-failed", action="store_true", help="Retry failed participants")

    # Status subcommand
    status_parser = subparsers.add_parser("status", help="Show task status")
    status_parser.add_argument("task_id", help="Task ID")

    # Conclude subcommand
    conclude_parser = subparsers.add_parser("conclude", help="Manually conclude discussion with decision")
    conclude_parser.add_argument("task_id", help="Task ID")
    conclude_parser.add_argument("decision", help="Final decision text")

    # Scan subcommand
    subparsers.add_parser("scan", help="Scan for incomplete tasks")

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
        # For discuss --mode=fast, allow running without init
        if args.command == "discuss" and hasattr(args, 'mode') and args.mode == "fast":
            # Fast mode: use git root or cwd, no init required
            if args.base_dir:
                base = Path(args.base_dir).resolve()
            else:
                # Try git root, fallback to cwd
                try:
                    import subprocess
                    result = subprocess.run(
                        ['git', 'rev-parse', '--show-toplevel'],
                        capture_output=True, text=True, check=True
                    )
                    base = Path(result.stdout.strip())
                except:
                    base = Path.cwd()
        elif args.command == "discuss":
            # Full mode discuss: auto-init if missing in local context
            from collab_paths import resolve_init_base_dir

            # Determine intended base directory
            intended_base = resolve_init_base_dir(args.base_dir) if args.base_dir else None
            if not intended_base:
                # Use git root or cwd as intended base
                try:
                    import subprocess
                    result = subprocess.run(
                        ['git', 'rev-parse', '--show-toplevel'],
                        capture_output=True, text=True, check=True
                    )
                    intended_base = Path(result.stdout.strip())
                except:
                    intended_base = Path.cwd()

            collab_dir = intended_base / ".omc" / "collaboration"

            # Auto-init if missing at intended location
            if not collab_dir.exists():
                print(f"ℹ️  No collaboration state at {intended_base}. Auto-initializing...")
                init_collaboration(str(intended_base), source="auto")
                print(f"✓ Collaboration initialized at: {collab_dir}")

            base = intended_base
        else:
            base = resolve_existing_base_dir(args.base_dir)

        if args.command == "scan":
            sys.exit(run_scan(base))
        elif args.command == "history":
            sys.exit(run_history(base, args.task_id, args.format, args.summary))
        elif args.command == "status":
            sys.exit(run_status(base, args.task_id))
        elif args.command == "conclude":
            sys.exit(run_conclude(base, args.task_id, args.decision))
        elif args.command == "resume":
            sys.exit(run_resume(base, args.task_id, args.retry_failed))
        elif args.command == "discuss":
            # Determine task_id and topic based on input format
            if args.topic_flag:
                # New format: --topic "..." (generate TASK-ID from topic)
                topic = args.topic_flag
                # Generate TASK-ID from topic: first 3 words + timestamp
                import re
                words = re.findall(r'\w+', topic)[:3]
                slug = "-".join(words).upper()
                task_id = f"DISCUSS-{slug}-{int(time.time())}"
            elif args.task_id and args.topic:
                # Old format: task_id topic (backward compatibility)
                task_id = args.task_id
                topic = args.topic
            else:
                print("❌ Error: Either provide --topic or both task_id and topic")
                print("Usage: collab_discuss.py discuss --topic \"...\" [--max-rounds 3]")
                print("   or: collab_discuss.py discuss TASK-ID \"topic\" [--participants ...]")
                sys.exit(1)

            participants = [p.strip() for p in args.participants.split(",")]
            sys.exit(run_discussion(base, task_id, topic, participants,
                                   args.max_rounds, hard_max_rounds=10,
                                   timeout_sec=args.timeout_sec, mode=args.mode))
        else:
            parser.print_help()
            sys.exit(1)

    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
