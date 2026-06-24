#!/usr/bin/env python3
"""Discussion orchestration for Claude-Codex-Gemini collaboration."""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Dict, Optional

from agentmemory_bridge import AgentMemoryBridge, dedupe as dedupe_memory_values
from agent_cli import run_codex, run_gemini, AgentReply
from collab_event import append_event, read_events, read_state
from collab_init import init_collaboration
from collab_paths import resolve_existing_base_dir, add_base_dir_arg
from collab_status_display import show_runtime_status
from discussion_enhancements import check_and_handle_doom_loop, auto_compact_if_needed
from models import Challenge, Conflict, ConsensusArtifact, Response
from rmux_utils import check_rmux_available, get_tmux_info
from collab_state import (
    init_task_state, load_task_state, save_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round, get_pending_participants, get_task_state_file
)


def make_response_id(task_id: str, round_num: int, agent: str) -> str:
    """Build a stable response ID used for cross-response references."""
    safe_agent = agent.lower().strip() or "unknown"
    return f"{task_id}-r{round_num}-{safe_agent}"


def normalize_string_list(value: Any) -> List[str]:
    """Return a clean list of strings from user/agent supplied JSON."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_challenges(value: Any) -> List[Dict[str, str]]:
    """Normalize targeted challenge dictionaries."""
    if not isinstance(value, list):
        return []

    challenges = []
    for item in value:
        if not isinstance(item, dict):
            continue
        challenge = Challenge(
            target_agent=str(item.get("target_agent", "")).strip(),
            target_response_id=str(item.get("target_response_id", "")).strip(),
            question=str(item.get("question", "")).strip(),
            rationale=str(item.get("rationale", "")).strip(),
        )
        if challenge.target_agent and challenge.target_response_id and challenge.question:
            challenges.append(challenge.to_dict())
    return challenges


def normalize_action_items(value: Any) -> List[Dict[str, Any]]:
    """Normalize action item dictionaries without requiring a separate schema import."""
    if not isinstance(value, list):
        return []

    action_items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task", "")).strip()
        owner = str(item.get("owner", "")).strip()
        if not task:
            continue
        action_items.append({
            "owner": owner,
            "task": task,
            "due": item.get("due"),
            "verification": item.get("verification"),
        })
    return action_items


VALID_CONSENSUS_SCOPES = {"project-specific", "cross-project", "global"}
CONSENSUS_TTL_DAYS = {
    "project-specific": 365,
    "cross-project": 730,
    "global": None,
}


def normalize_consensus_scope(value: Optional[str]) -> Optional[str]:
    """Normalize a user or model supplied consensus scope."""
    if value is None:
        return None

    normalized = str(value).strip().lower().replace("_", "-")
    aliases = {
        "project": "project-specific",
        "current-project": "project-specific",
        "project-specific": "project-specific",
        "cross": "cross-project",
        "cross-project": "cross-project",
        "global": "global",
    }
    scope = aliases.get(normalized)
    if scope not in VALID_CONSENSUS_SCOPES:
        raise ValueError(
            f"Invalid consensus scope: {value}. "
            "Expected project-specific, cross-project, or global."
        )
    return scope


def extract_text_for_scope(*values: Any) -> str:
    """Join nested values into lowercase text for scope heuristics."""
    parts = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            for key, nested in value.items():
                parts.append(str(key))
                parts.append(extract_text_for_scope(nested))
        elif isinstance(value, list):
            parts.append(extract_text_for_scope(*value))
        else:
            parts.append(str(value))
    return " ".join(part for part in parts if part).lower()


def detect_project_scope(
    topic: str,
    decision: str = "",
    evidence: Optional[List[str]] = None,
    action_items: Optional[List[Dict[str, Any]]] = None,
    requested_scope: Optional[str] = None,
) -> str:
    """Detect whether consensus is project-specific, cross-project, or global."""
    if requested_scope:
        return normalize_consensus_scope(requested_scope) or "project-specific"

    text = extract_text_for_scope(topic, decision, evidence or [], action_items or [])

    global_markers = [
        "global",
        "all projects",
        "all repositories",
        "organization-wide",
        "org-wide",
        "workspace-wide",
        "全局",
        "所有项目",
        "全部项目",
    ]
    if any(marker in text for marker in global_markers):
        return "global"

    project_specific_markers = [
        "this repo",
        "this repository",
        "current project",
        "local file",
        ".omc/",
        "scripts/",
        "tests/",
        "docs/",
        "本项目",
        "当前项目",
    ]
    if any(marker in text for marker in project_specific_markers):
        return "project-specific"

    cross_project_markers = [
        "cross-project",
        "multiple projects",
        "shared",
        "reusable",
        "portable",
        "common protocol",
        "architecture",
        "integration",
        "agentmemory",
        "skill",
        "collab",
        "iii-sdk",
        "跨项目",
        "多项目",
        "共享",
        "复用",
        "通用",
        "架构",
        "协议",
    ]
    if any(marker in text for marker in cross_project_markers):
        return "cross-project"

    return "project-specific"


def project_name_for_memory(base_dir: Path) -> str:
    """Return the current project namespace for agentmemory."""
    return base_dir.name or "collab"


def memory_projects_for_recall(base_dir: Path, requested_scope: Optional[str] = None) -> List[str]:
    """Return agentmemory project namespaces to query before discussion."""
    current_project = project_name_for_memory(base_dir)
    scope = normalize_consensus_scope(requested_scope) if requested_scope else None
    if scope == "global":
        return ["global"]
    if scope == "cross-project":
        return dedupe_memory_values([current_project, "cross-project", "global"])
    return dedupe_memory_values([current_project, "cross-project", "global"])


def memory_project_for_scope(base_dir: Path, project_scope: str) -> str:
    """Map consensus scope to an agentmemory project namespace."""
    if project_scope == "global":
        return "global"
    if project_scope == "cross-project":
        return "cross-project"
    return project_name_for_memory(base_dir)


def summarize_memory_hit(hit: Dict[str, Any], max_len: int = 240) -> str:
    """Return a compact display string for a recalled memory hit."""
    content = hit.get("content") or hit.get("text") or hit.get("summary") or hit.get("title") or ""
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False, sort_keys=True)
    content = str(content).replace("\n", " ").strip()
    if len(content) > max_len:
        return content[: max_len - 3] + "..."
    return content


def parse_memory_content(hit: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON memory content if possible."""
    content = hit.get("content") or hit.get("text") or hit.get("memory") or {}
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def get_consensus_field(consensus: Any, field: str, default: Any = None) -> Any:
    """Read a field from a memory hit, parsed content, or object-like consensus."""
    if isinstance(consensus, dict):
        parsed = parse_memory_content(consensus)
        if field in parsed:
            return parsed.get(field)
        if field in consensus:
            return consensus.get(field)
        if field == "id":
            return consensus.get("id") or consensus.get("memory_id") or consensus.get("uuid")
        return default
    return getattr(consensus, field, default)


def consensus_id(consensus: Any) -> Optional[str]:
    """Return a stable identifier from a historical consensus hit."""
    value = get_consensus_field(consensus, "id")
    return str(value) if value else None


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp into an aware datetime when possible."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def consensus_expires_at(created_at: Optional[str], ttl_days: Optional[int]) -> Optional[str]:
    """Calculate an expiry timestamp for a consensus artifact."""
    if ttl_days is None:
        return None
    created = parse_iso_datetime(created_at) or datetime.now(timezone.utc)
    return (created + timedelta(days=ttl_days)).isoformat()


def is_consensus_expired(consensus: Any, now: Optional[datetime] = None) -> bool:
    """Return whether a historical consensus is past its TTL/expiry timestamp."""
    status = str(get_consensus_field(consensus, "status", "") or "").lower()
    if status == "expired":
        return True

    expires_at = parse_iso_datetime(get_consensus_field(consensus, "expires_at"))
    if not expires_at:
        created_at = get_consensus_field(consensus, "created_at")
        ttl_days = get_consensus_field(consensus, "ttl_days")
        try:
            ttl = int(ttl_days) if ttl_days is not None else None
        except (TypeError, ValueError):
            ttl = None
        expires_text = consensus_expires_at(created_at, ttl)
        expires_at = parse_iso_datetime(expires_text)
    if not expires_at:
        return False

    return (now or datetime.now(timezone.utc)) >= expires_at


def build_consensus_namespace(base_dir: Path, project_scope: str) -> str:
    """Build explicit namespace metadata for consensus memory."""
    scope = normalize_consensus_scope(project_scope) or "project-specific"
    if scope == "global":
        return "global"
    if scope == "cross-project":
        return "cross-project"
    return f"project:{project_name_for_memory(base_dir)}"


def build_consensus_permission(project_scope: str, participants: List[str]) -> Dict[str, Any]:
    """Return read/write/override policy metadata for a consensus scope."""
    scope = normalize_consensus_scope(project_scope) or "project-specific"
    actors = dedupe_preserve_order(["system", *participants])
    if scope == "global":
        return {
            "read": ["all"],
            "write": ["system", "maintainer"],
            "override": ["system", "maintainer"],
            "participants": participants,
        }
    if scope == "cross-project":
        return {
            "read": ["all"],
            "write": actors,
            "override": dedupe_preserve_order([*actors, "maintainer"]),
            "participants": participants,
        }
    return {
        "read": ["system", "project", *participants],
        "write": actors,
        "override": actors,
        "participants": participants,
    }


def has_consensus_permission(permission: Dict[str, Any], actor: str, action: str) -> bool:
    """Check whether an actor is allowed by consensus permission metadata."""
    allowed = permission.get(action, [])
    if not isinstance(allowed, list):
        return False
    actor_key = str(actor or "").strip()
    return "all" in allowed or actor_key in allowed


def detect_consensus_version(topic: str, related_consensus: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the latest same-topic consensus and return next version metadata."""
    topic_key = topic.strip().lower()
    result = {"version": 1, "previous_version_id": None}
    if not topic_key:
        return result

    latest_version = 0
    latest_id = None
    for hit in related_consensus:
        memory_type = str(get_consensus_field(hit, "type", "") or "")
        if memory_type != "discussion_consensus":
            continue
        old_topic = str(get_consensus_field(hit, "topic", "") or "").strip().lower()
        if old_topic == topic_key:
            memory_id = consensus_id(hit)
            try:
                version = int(get_consensus_field(hit, "version", 1) or 1)
            except (TypeError, ValueError):
                version = 1
            if version >= latest_version:
                latest_version = version
                latest_id = str(memory_id) if memory_id else None

    if latest_version:
        result["version"] = latest_version + 1
        result["previous_version_id"] = latest_id
    return result


def detect_supersedes(topic: str, related_consensus: List[Dict[str, Any]]) -> Optional[str]:
    """Choose a directly matching historical consensus to supersede, if any."""
    version_info = detect_consensus_version(topic, related_consensus)
    return version_info.get("previous_version_id")


def significant_terms(text: str) -> set:
    """Extract coarse terms for overlap checks in semantic-opposite heuristics."""
    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "into", "use",
        "using", "add", "remove", "disable", "enable", "avoid", "require",
        "requires", "required", "discussion", "consensus", "topic", "new",
        "old", "decision", "方案", "讨论", "共识", "实现", "功能", "使用",
    }
    terms = set()
    for word in re.findall(r"[A-Za-z0-9_\-]{3,}|[\u4e00-\u9fff]{2,}", text.lower()):
        if word not in stop_words:
            terms.add(word)
    return terms


def intent_markers(text: str) -> set:
    """Classify broad intent markers used by semantic-opposite detection."""
    lowered = text.lower()
    markers = set()
    phrase_groups = {
        "enable": ["enable", "add", "use", "adopt", "persist", "save", "store", "allow", "require", "启用", "使用", "保存", "持久化", "允许", "要求"],
        "disable": ["disable", "remove", "delete", "avoid", "stop", "drop", "deprecate", "do not use", "don't use", "do not save", "禁止", "禁用", "移除", "删除", "避免", "不要", "不使用"],
        "global": ["global", "all projects", "organization-wide", "workspace-wide", "全局", "所有项目", "全部项目"],
        "project": ["project-specific", "current project", "this repo", "local only", "per-project", "本项目", "当前项目", "项目级"],
        "mandatory": ["must", "require", "mandatory", "always", "必须", "要求", "强制"],
        "optional": ["optional", "may", "best effort", "graceful", "fallback", "可选", "按需", "降级"],
    }
    for marker, phrases in phrase_groups.items():
        if any(phrase in lowered for phrase in phrases):
            markers.add(marker)
    return markers


def semantic_opposite(new_topic: str, old_decision: str) -> bool:
    """Heuristic semantic-opposite check for topic-vs-decision contradictions."""
    if not new_topic or not old_decision:
        return False

    topic_markers = intent_markers(new_topic)
    decision_markers = intent_markers(old_decision)
    opposite_pairs = [
        ("enable", "disable"),
        ("global", "project"),
        ("mandatory", "optional"),
    ]
    has_opposite_intent = any(
        (left in topic_markers and right in decision_markers)
        or (right in topic_markers and left in decision_markers)
        for left, right in opposite_pairs
    )
    if not has_opposite_intent:
        return False

    topic_terms = significant_terms(new_topic)
    decision_terms = significant_terms(old_decision)
    if topic_terms and decision_terms:
        return bool(topic_terms & decision_terms)

    combined = f"{new_topic} {old_decision}".lower()
    return any(term in combined for term in ["agentmemory", "consensus", "共识", "持久化"])


def check_conflicts(new_topic: str, related: List[Any]) -> List[Dict[str, Any]]:
    """Detect semantic conflicts between a new discussion topic and old consensus."""
    conflicts = []
    for old in related or []:
        if is_consensus_expired(old):
            continue
        old_decision = str(get_consensus_field(old, "decision", "") or "")
        if not semantic_opposite(new_topic, old_decision):
            continue

        try:
            confidence = float(get_consensus_field(old, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        old_id = consensus_id(old) or "unknown"
        conflict = Conflict(
            old_consensus_id=old_id,
            reason=f"New topic contradicts historical decision: {old_decision}",
            severity="high" if confidence > 0.8 else "medium",
            old_decision=old_decision,
            confidence=confidence,
            project=str(get_consensus_field(old, "project", "") or get_consensus_field(old, "namespace", "") or "") or None,
        )
        conflicts.append(conflict.to_dict())
    return conflicts


def filter_active_consensus(related: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Split historical consensus hits into active and expired lists."""
    active = []
    expired = []
    for hit in related or []:
        item = dict(hit)
        if is_consensus_expired(item):
            item["status"] = "expired"
            expired.append(item)
        else:
            active.append(item)
    return {"active": active, "expired": expired}


def extract_consensus_tags(topic: str, project_scope: str, participants: List[str]) -> List[str]:
    """Generate compact concept tags for consensus storage."""
    import re

    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "into", "are",
        "讨论", "方案", "根据", "实现", "功能", "接入",
    }
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z0-9_\-]{3,}|[\u4e00-\u9fff]{2,}", topic)
        if word.lower() not in stop_words
    ]
    return dedupe_preserve_order([
        "discussion_consensus",
        project_scope,
        *participants,
        *words[:8],
    ])


def estimate_consensus_confidence(final_consensus: Dict[str, Any]) -> float:
    """Estimate confidence from consensus metadata."""
    confidence = 0.85 if final_consensus.get("reached") else 0.45
    if final_consensus.get("evidence"):
        confidence += 0.05
    if final_consensus.get("action_items"):
        confidence += 0.05
    if final_consensus.get("dissent"):
        confidence -= 0.10
    if final_consensus.get("blocking_issues"):
        confidence -= 0.10
    return max(0.0, min(1.0, round(confidence, 2)))


def build_consensus_artifact(
    base_dir: Path,
    task_id: str,
    topic: str,
    participants: List[str],
    task_state: Dict[str, Any],
    requested_scope: Optional[str] = None,
) -> ConsensusArtifact:
    """Build the structured consensus artifact persisted to agentmemory."""
    final_consensus = task_state.get("final_consensus", {})
    decision = str(final_consensus.get("decision") or "")
    evidence = normalize_string_list(final_consensus.get("evidence", []))
    action_items = normalize_action_items(final_consensus.get("action_items", []))
    project_scope = detect_project_scope(
        topic,
        decision,
        evidence,
        action_items,
        requested_scope=requested_scope,
    )
    related = task_state.get("agentmemory", {}).get("related_consensus", [])
    created_at = datetime.now(timezone.utc).isoformat()
    ttl_days = CONSENSUS_TTL_DAYS.get(project_scope)
    version_info = detect_consensus_version(topic, related)
    namespace = build_consensus_namespace(base_dir, project_scope)
    permission = build_consensus_permission(project_scope, participants)
    return ConsensusArtifact(
        topic=topic,
        participants=participants,
        decision=decision,
        dissent=final_consensus.get("dissent"),
        evidence=evidence,
        action_items=action_items,
        project_scope=project_scope,
        confidence=estimate_consensus_confidence(final_consensus),
        supersedes=version_info.get("previous_version_id"),
        tags=extract_consensus_tags(topic, project_scope, participants),
        task_id=task_id,
        round=final_consensus.get("round"),
        created_at=created_at,
        namespace=namespace,
        permission=permission,
        ttl_days=ttl_days,
        expires_at=consensus_expires_at(created_at, ttl_days),
        version=version_info["version"],
        previous_version_id=version_info.get("previous_version_id"),
        status="active",
    )


def recall_related_consensus(
    base_dir: Path,
    topic: str,
    requested_scope: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Recall related historical consensus from agentmemory."""
    if os.environ.get("CCG_AGENTMEMORY_DISABLED", "").lower() == "true":
        return {
            "enabled": False,
            "related_consensus": [],
            "expired_consensus": [],
            "potential_conflicts": [],
            "error": "disabled by CCG_AGENTMEMORY_DISABLED",
        }

    projects = memory_projects_for_recall(base_dir, requested_scope)
    try:
        bridge = AgentMemoryBridge()
        related = bridge.recall_consensus(topic, projects, limit=limit)
        split = filter_active_consensus(related)
        active = split["active"]
        conflicts = check_conflicts(topic, active)
        return {
            "enabled": True,
            "projects": projects,
            "related_consensus": active,
            "expired_consensus": split["expired"],
            "potential_conflicts": conflicts,
            "error": None,
        }
    except Exception as exc:
        return {
            "enabled": False,
            "projects": projects,
            "related_consensus": [],
            "expired_consensus": [],
            "potential_conflicts": [],
            "error": str(exc),
        }


def save_consensus_to_agentmemory(
    base_dir: Path,
    task_id: str,
    task_state: Dict[str, Any],
    requested_scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist final consensus to agentmemory if available."""
    final_consensus = task_state.get("final_consensus", {})
    if not final_consensus.get("reached"):
        return {"saved": False, "reason": "consensus_not_reached"}

    agentmemory_state = task_state.setdefault("agentmemory", {})
    if agentmemory_state.get("saved_consensus_id"):
        return {
            "saved": True,
            "already_saved": True,
            "memory_id": agentmemory_state.get("saved_consensus_id"),
        }

    artifact = build_consensus_artifact(
        base_dir,
        task_id,
        task_state.get("topic", ""),
        task_state.get("participants", []),
        task_state,
        requested_scope=requested_scope or agentmemory_state.get("requested_scope"),
    )
    project = memory_project_for_scope(base_dir, artifact.project_scope)
    if not has_consensus_permission(artifact.permission, "system", "write"):
        agentmemory_state["consensus_artifact"] = artifact.to_dict()
        agentmemory_state["save_error"] = "system actor lacks write permission for consensus scope"
        return {"saved": False, "project": project, "artifact": artifact.to_dict(), "error": agentmemory_state["save_error"]}

    if os.environ.get("CCG_AGENTMEMORY_DISABLED", "").lower() == "true":
        agentmemory_state["consensus_artifact"] = artifact.to_dict()
        agentmemory_state["save_error"] = "disabled by CCG_AGENTMEMORY_DISABLED"
        return {"saved": False, "artifact": artifact.to_dict(), "error": agentmemory_state["save_error"]}

    try:
        bridge = AgentMemoryBridge()
        result = bridge.save_consensus(artifact.to_dict(), project=project)
        memory_id = None
        if isinstance(result, dict):
            memory = result.get("memory") if isinstance(result.get("memory"), dict) else {}
            memory_id = result.get("id") or result.get("memory_id") or memory.get("id")
        agentmemory_state["consensus_artifact"] = artifact.to_dict()
        agentmemory_state["save_result"] = result
        if memory_id:
            agentmemory_state["saved_consensus_id"] = memory_id
        return {
            "saved": True,
            "project": project,
            "artifact": artifact.to_dict(),
            "result": result,
            "memory_id": memory_id,
        }
    except Exception as exc:
        agentmemory_state["consensus_artifact"] = artifact.to_dict()
        agentmemory_state["save_error"] = str(exc)
        return {"saved": False, "project": project, "artifact": artifact.to_dict(), "error": str(exc)}


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
    artifacts: List[str],
    previous_responses: Optional[List[Dict[str, Any]]] = None,
    open_questions: Optional[List[str]] = None,
    targeted_challenges: Optional[List[Dict[str, str]]] = None,
    pre_discuss: Optional[Dict[str, str]] = None,
    related_consensus: Optional[List[Dict[str, Any]]] = None,
    potential_conflicts: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Save discussion context to file, return relative path."""
    context_dir = base_dir / ".collab" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{task_id}-r{round_num}-context.md"
    context_path = context_dir / filename

    content = f"""# Discussion Context

**Task:** {task_id}
**Round:** {round_num}

## Topic

{topic}

"""

    if related_consensus:
        content += "## Related Historical Consensus\n\n"
        for idx, item in enumerate(related_consensus, start=1):
            memory_id = item.get("id") or item.get("memory_id") or item.get("uuid") or f"related-{idx}"
            project = item.get("project") or item.get("namespace") or "unknown"
            title = item.get("title") or item.get("name") or "Historical consensus"
            content += f"### {memory_id} ({project})\n\n"
            content += f"Title: {title}\n\n"
            content += f"{summarize_memory_hit(item)}\n\n"

    if potential_conflicts:
        content += "## Potential Consensus Conflicts\n\n"
        for conflict in potential_conflicts:
            content += (
                f"- {conflict.get('severity', 'medium').upper()}: "
                f"{conflict.get('old_consensus_id', 'unknown')} - "
                f"{conflict.get('reason', '')}\n"
            )
        content += "\n"

    if pre_discuss:
        content += f"""## Pre-Discuss Initial Analysis

Response ID: {pre_discuss.get("response_id", "")}
Artifact: {pre_discuss.get("artifact", "")}

{pre_discuss.get("summary", "")}

"""

    if history:
        content += f"""## Previous Discussion

{history}

"""

    if previous_responses:
        content += "## Previous Responses\n\n"
        for response in previous_responses:
            content += f"### {response.get('id', '')} ({response.get('agent', 'unknown')})\n\n"
            decision = response.get("decision") or response.get("content") or ""
            if decision:
                content += f"Decision: {decision}\n\n"
            reasoning = response.get("reasoning") or ""
            if reasoning:
                content += f"Reasoning: {reasoning}\n\n"
            if response.get("blocking_issues"):
                content += "Blocking issues:\n"
                for issue in response["blocking_issues"]:
                    content += f"- {issue}\n"
                content += "\n"
            if response.get("targeted_challenges"):
                content += "Targeted challenges raised:\n"
                for challenge in response["targeted_challenges"]:
                    content += (
                        f"- To {challenge.get('target_agent', 'unknown')} "
                        f"on {challenge.get('target_response_id', '')}: "
                        f"{challenge.get('question', '')}\n"
                    )
                content += "\n"

    if open_questions:
        content += "## Open Questions\n\n"
        for question in open_questions:
            content += f"- {question}\n"
        content += "\n"

    if targeted_challenges:
        content += "## Unresolved Targeted Challenges\n\n"
        for challenge in targeted_challenges:
            content += (
                f"- To {challenge.get('target_agent', 'unknown')} "
                f"on {challenge.get('target_response_id', '')}: "
                f"{challenge.get('question', '')} "
                f"(Rationale: {challenge.get('rationale', '')})\n"
            )
        content += "\n"

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
    context_file: Optional[str] = None,
    previous_responses: Optional[List[Dict[str, Any]]] = None,
    open_questions: Optional[List[str]] = None,
    targeted_challenges: Optional[List[Dict[str, str]]] = None,
    related_consensus: Optional[List[Dict[str, Any]]] = None,
    potential_conflicts: Optional[List[Dict[str, Any]]] = None,
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
  "reasoning": "why you agree/disagree",
  "previous_responses": ["response_id_you_directly_addressed"],
  "targeted_challenges": [
    {{
      "target_agent": "agent name",
      "target_response_id": "response id",
      "question": "specific challenge or question",
      "rationale": "why this challenge matters"
    }}
  ],
  "dissent": "reservation or minority opinion, or null",
  "evidence": ["specific evidence supporting your position"],
  "action_items": [
    {{"owner": "agent/person", "task": "specific action", "due": "optional", "verification": "how to verify"}}
  ]
}}
[RESPONSE_END]

IMPORTANT: Your response MUST be wrapped between [RESPONSE_START] and [RESPONSE_END] markers.
Directly cite at least one relevant Previous Response ID when prior responses exist.
Consider Related Historical Consensus when present, and call out conflicts explicitly.
Treat Potential Consensus Conflicts as required review items when present.
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
  "reasoning": "why you agree/disagree",
  "previous_responses": ["response_id_you_directly_addressed"],
  "targeted_challenges": [
    {{
      "target_agent": "agent name",
      "target_response_id": "response id",
      "question": "specific challenge or question",
      "rationale": "why this challenge matters"
    }}
  ],
  "dissent": "reservation or minority opinion, or null",
  "evidence": ["specific evidence supporting your position"],
  "action_items": [
    {{"owner": "agent/person", "task": "specific action", "due": "optional", "verification": "how to verify"}}
  ]
}}
[RESPONSE_END]

IMPORTANT: Your response MUST be wrapped between [RESPONSE_START] and [RESPONSE_END] markers.
Directly cite at least one relevant Previous Response ID when prior responses exist.
Consider Related Historical Consensus when present, and call out conflicts explicitly.
Treat Potential Consensus Conflicts as required review items when present.
Output ONLY the markers and JSON, nothing else.

"""

    if related_consensus:
        prompt += "Related historical consensus:\n"
        for idx, item in enumerate(related_consensus, start=1):
            memory_id = item.get("id") or item.get("memory_id") or f"related-{idx}"
            project = item.get("project") or "unknown"
            prompt += f"- {memory_id} ({project}): {summarize_memory_hit(item)}\n"
        prompt += "\n"

    if potential_conflicts:
        prompt += "Potential consensus conflicts:\n"
        for conflict in potential_conflicts:
            prompt += (
                f"- {conflict.get('severity', 'medium').upper()} "
                f"{conflict.get('old_consensus_id', 'unknown')}: "
                f"{conflict.get('reason', '')}\n"
            )
        prompt += "\n"

    if history:
        prompt += f"Previous discussion:\n{history}\n\n"

    if previous_responses:
        prompt += "Previous responses available for direct citation:\n"
        for response in previous_responses:
            prompt += (
                f"- {response.get('id', '')} ({response.get('agent', 'unknown')}): "
                f"{response.get('decision') or response.get('content') or ''}\n"
            )
        prompt += "\n"

    if open_questions:
        prompt += "Open questions:\n"
        for question in open_questions:
            prompt += f"- {question}\n"
        prompt += "\n"

    if targeted_challenges:
        prompt += "Unresolved targeted challenges:\n"
        for challenge in targeted_challenges:
            prompt += (
                f"- To {challenge.get('target_agent', 'unknown')} "
                f"on {challenge.get('target_response_id', '')}: "
                f"{challenge.get('question', '')}\n"
            )
        prompt += "\n"

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
        "dissent": task_state['final_consensus'].get('dissent'),
        "evidence": task_state['final_consensus'].get('evidence', []),
        "tasks": task_state['final_consensus'].get('action_items', []),
        "blocking_issues": task_state['final_consensus'].get('blocking_issues', [])
    }

    output_path = base_dir / ".collab/tasks" / task_id / "consensus.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(consensus, f, indent=2, ensure_ascii=False)


def check_consensus(replies: List[AgentReply]) -> Dict[str, Any]:
    """Return detailed consensus status and dissent from agent replies."""
    if not replies:
        return {
            "consensus": False,
            "blocking_issues": [],
            "dissent": None,
            "agreeing_agents": [],
            "dissenting_agents": [],
            "evidence": [],
            "action_items": [],
        }

    all_agree = True
    blocking_issues = []
    dissent_parts = []
    agreeing_agents = []
    dissenting_agents = []
    evidence = []
    action_items = []

    for reply in replies:
        parsed = reply.parsed
        if isinstance(parsed, dict):
            consensus = parsed.get("consensus", False)
            issues = parsed.get("blocking_issues", [])

            if consensus:
                agreeing_agents.append(reply.agent)
            else:
                all_agree = False
                dissenting_agents.append(reply.agent)

            if isinstance(issues, list):
                blocking_issues.extend(str(issue) for issue in issues if str(issue).strip())

            dissent = parsed.get("dissent")
            if dissent:
                dissent_parts.append(f"[{reply.agent}] {dissent}")
            elif not consensus:
                reason = parsed.get("reasoning") or parsed.get("decision") or "No dissent detail provided"
                dissent_parts.append(f"[{reply.agent}] {reason}")

            evidence.extend(normalize_string_list(parsed.get("evidence", [])))
            action_items.extend(normalize_action_items(parsed.get("action_items", [])))
        else:
            all_agree = False
            dissenting_agents.append(reply.agent)
            dissent_parts.append(f"[{reply.agent}] Unparseable response")

    return {
        "consensus": all_agree,
        "blocking_issues": blocking_issues,
        "dissent": "\n".join(dissent_parts) if dissent_parts else None,
        "agreeing_agents": agreeing_agents,
        "dissenting_agents": dissenting_agents,
        "evidence": evidence,
        "action_items": action_items,
    }


def judge_consensus(replies: List[AgentReply]) -> tuple[bool, List[str]]:
    """Judge if consensus reached from agent replies.

    Kept as a compatibility wrapper for existing callers/tests.
    """
    detail = check_consensus(replies)
    return detail["consensus"], detail["blocking_issues"]


def save_artifact(base_dir: Path, task_id: str, round_num: int, agent: str, content: str) -> str:
    """Save discussion artifact to file."""
    artifacts_dir = base_dir / ".collab" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{task_id}-discuss-r{round_num}-{agent}-{timestamp}.md"
    artifact_path = artifacts_dir / filename

    artifact_path.write_text(content)
    return str(artifact_path.relative_to(base_dir))


def dedupe_preserve_order(items: List[str]) -> List[str]:
    """Deduplicate strings while preserving first-seen order."""
    seen = set()
    result = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def normalize_parsed_response(parsed: Dict[str, Any], task_id: str, round_num: int, agent: str) -> Dict[str, Any]:
    """Normalize a parsed agent response to the Phase 1 protocol shape."""
    normalized = dict(parsed)
    normalized["id"] = str(normalized.get("id") or make_response_id(task_id, round_num, agent))
    normalized["previous_responses"] = normalize_string_list(normalized.get("previous_responses", []))
    normalized["targeted_challenges"] = normalize_challenges(normalized.get("targeted_challenges", []))
    normalized["blocking_issues"] = normalize_string_list(normalized.get("blocking_issues", []))
    normalized["evidence"] = normalize_string_list(normalized.get("evidence", []))
    normalized["action_items"] = normalize_action_items(normalized.get("action_items", []))
    return normalized


def create_pre_discuss_analysis(base_dir: Path, task_id: str, topic: str) -> Dict[str, str]:
    """Create Claude's initial analysis document for the Pre-discuss stage."""
    response_id = make_response_id(task_id, 0, "claude")
    content = f"""# Pre-Discuss Initial Analysis

Response ID: {response_id}
Agent: claude

## Topic

{topic}

## Initial Analysis

- Clarify the decision or implementation change requested by the topic.
- Identify compatibility, state persistence, and verification risks before participants respond.
- Ask Codex and Gemini to challenge this framing directly and cite prior response IDs.

## Open Questions

- What assumptions in the initial framing are weakest?
- Which compatibility contracts must remain stable?
- What evidence or tests are required before concluding?
"""
    artifact_path = save_artifact(base_dir, task_id, 0, "claude", content)
    return {
        "response_id": response_id,
        "agent": "claude",
        "artifact": artifact_path,
        "summary": "Claude initial framing: clarify scope, challenge assumptions, preserve compatibility, and require evidence.",
        "content": content,
    }


def ensure_pre_discuss(
    base_dir: Path,
    task_id: str,
    topic: str,
    task_state: Dict[str, Any],
    artifacts_refs: List[str],
) -> Dict[str, Any]:
    """Ensure the task has a Pre-discuss initial analysis artifact."""
    pre_discuss = task_state.get("pre_discuss")
    if pre_discuss:
        artifact = pre_discuss.get("artifact")
        if artifact and artifact not in artifacts_refs:
            artifacts_refs.append(artifact)
        return task_state

    pre_discuss = create_pre_discuss_analysis(base_dir, task_id, topic)
    task_state["pre_discuss"] = pre_discuss
    files = task_state.setdefault("artifacts", {}).setdefault("files", [])
    if pre_discuss["artifact"] not in files:
        files.append(pre_discuss["artifact"])
    if pre_discuss["artifact"] not in artifacts_refs:
        artifacts_refs.append(pre_discuss["artifact"])
    save_task_state(base_dir, task_id, task_state)
    return task_state


def collect_protocol_context(task_state: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    """Collect previous responses, open questions, and challenges from task state."""
    previous_responses = []
    open_questions = []
    targeted_challenges = []

    pre_discuss = task_state.get("pre_discuss")
    if pre_discuss:
        previous_responses.append({
            "id": pre_discuss.get("response_id") or make_response_id(task_id, 0, "claude"),
            "agent": "claude",
            "content": pre_discuss.get("summary", ""),
            "decision": pre_discuss.get("summary", ""),
            "reasoning": "Initial framing for the discussion.",
            "blocking_issues": [],
            "previous_responses": [],
            "targeted_challenges": [],
        })
        open_questions.extend([
            "What assumptions in Claude's initial framing are weakest?",
            "Which compatibility contracts must remain stable?",
            "What evidence or tests are required before concluding?",
        ])

    for round_state in task_state.get("rounds", []):
        round_num = round_state.get("round_number")
        if isinstance(round_num, int):
            consensus_check = round_state.get("consensus_check", {})
            open_questions.extend(normalize_string_list(consensus_check.get("blocking_issues", [])))

            for participant in round_state.get("participants", []):
                if participant.get("status") != "completed":
                    continue
                agent = participant.get("agent", "unknown")
                parsed = participant.get("parsed_response")
                if not isinstance(parsed, dict):
                    continue
                normalized = normalize_parsed_response(parsed, task_id, round_num, agent)
                challenges = normalized.get("targeted_challenges", [])
                response = Response(
                    id=normalized["id"],
                    agent=agent,
                    content=normalized.get("decision") or normalized.get("reasoning") or "",
                    previous_responses=normalized.get("previous_responses", []),
                    targeted_challenges=[Challenge(**challenge) for challenge in challenges],
                    consensus=normalized.get("consensus"),
                    decision=normalized.get("decision"),
                    reasoning=normalized.get("reasoning"),
                    blocking_issues=normalized.get("blocking_issues", []),
                    dissent=normalized.get("dissent"),
                    evidence=normalized.get("evidence", []),
                )
                response_dict = response.to_dict()
                previous_responses.append(response_dict)
                open_questions.extend(response_dict.get("blocking_issues", []))
                targeted_challenges.extend(challenges)

    return {
        "previous_responses": previous_responses,
        "open_questions": dedupe_preserve_order(open_questions),
        "targeted_challenges": targeted_challenges,
    }


def parse_discussion_artifacts(base_dir: Path, task_id: str) -> List[Dict]:
    """Parse discussion artifacts for a task."""
    artifacts_dir = base_dir / ".collab" / "artifacts"
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
                "id": content.get("id") or make_response_id(task_id, round_num, agent),
                "consensus": content.get("consensus", False),
                "decision": content.get("decision", ""),
                "reasoning": content.get("reasoning", ""),
                "blocking_issues": normalize_string_list(content.get("blocking_issues", [])),
                "previous_responses": normalize_string_list(content.get("previous_responses", [])),
                "targeted_challenges": normalize_challenges(content.get("targeted_challenges", [])),
                "dissent": content.get("dissent"),
                "evidence": normalize_string_list(content.get("evidence", [])),
                "action_items": normalize_action_items(content.get("action_items", [])),
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
            if item.get("previous_responses"):
                output.append(f"  References: {', '.join(item['previous_responses'])}")
            if item.get("targeted_challenges"):
                output.append(f"  Challenges: {len(item['targeted_challenges'])}")
            if item.get("dissent"):
                output.append(f"  Dissent: {item['dissent']}")
            if item["blocking_issues"]:
                output.append(f"  Blocking: {', '.join(item['blocking_issues'])}")
            output.append("")

    return "\n".join(output)


def quality_rate(numerator: int, denominator: int) -> float:
    """Return a rounded 0..1 metric rate."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def is_executable_action_item(item: Dict[str, Any]) -> bool:
    """Action item is executable when it has owner/task/due/verification."""
    if not isinstance(item, dict):
        return False
    return all(str(item.get(field) or "").strip() for field in ("owner", "task", "due", "verification"))


def iter_completed_responses(task_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return parsed completed participant responses from a task state."""
    responses = []
    for round_state in task_state.get("rounds", []):
        for participant in round_state.get("participants", []):
            parsed = participant.get("parsed_response")
            if participant.get("status") == "completed" and isinstance(parsed, dict):
                responses.append(parsed)
    return responses


def calculate_quality_metrics(task_state: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Phase 3 quality metrics for a single discussion task."""
    responses = iter_completed_responses(task_state)
    total_responses = len(responses)
    cited_responses = sum(1 for response in responses if normalize_string_list(response.get("previous_responses", [])))

    final_consensus = task_state.get("final_consensus", {})
    action_items = normalize_action_items(final_consensus.get("action_items", []))
    if not action_items:
        for response in responses:
            action_items.extend(normalize_action_items(response.get("action_items", [])))

    executable_actions = sum(1 for item in action_items if is_executable_action_item(item))
    related_count = len(task_state.get("agentmemory", {}).get("related_consensus", []) or [])

    return {
        "citation_rate": {
            "cited_responses": cited_responses,
            "total_responses": total_responses,
            "rate": quality_rate(cited_responses, total_responses),
            "target": 0.60,
        },
        "action_item_executable_rate": {
            "executable_action_items": executable_actions,
            "total_action_items": len(action_items),
            "rate": quality_rate(executable_actions, len(action_items)),
            "target": 0.80,
        },
        "history_reuse_hit_rate": {
            "hit": related_count > 0,
            "related_consensus_count": related_count,
            "rate": 1.0 if related_count > 0 else 0.0,
            "target": 0.40,
        },
    }


def attach_quality_metrics(task_state: Dict[str, Any]) -> Dict[str, Any]:
    """Attach latest quality metrics to task state."""
    task_state["quality_metrics"] = calculate_quality_metrics(task_state)
    return task_state


def load_all_discussion_states(base_dir: Path) -> List[Dict[str, Any]]:
    """Load all valid discussion task states."""
    state_dir = base_dir / ".collab" / "state"
    if not state_dir.exists():
        return []

    states = []
    for state_file in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("task_id") and data.get("topic"):
            states.append(data)
    return states


def aggregate_quality_metrics(states: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate Phase 3 metrics across discussion tasks."""
    total_responses = 0
    cited_responses = 0
    total_actions = 0
    executable_actions = 0
    reuse_hits = 0

    task_summaries = []
    for state in states:
        metrics = calculate_quality_metrics(state)
        citation = metrics["citation_rate"]
        actions = metrics["action_item_executable_rate"]
        reuse = metrics["history_reuse_hit_rate"]

        total_responses += citation["total_responses"]
        cited_responses += citation["cited_responses"]
        total_actions += actions["total_action_items"]
        executable_actions += actions["executable_action_items"]
        reuse_hits += 1 if reuse["hit"] else 0
        task_summaries.append({
            "task_id": state.get("task_id"),
            "topic": state.get("topic"),
            "status": state.get("status"),
            "metrics": metrics,
        })

    total_tasks = len(states)
    return {
        "total_tasks": total_tasks,
        "citation_rate": {
            "cited_responses": cited_responses,
            "total_responses": total_responses,
            "rate": quality_rate(cited_responses, total_responses),
            "target": 0.60,
        },
        "action_item_executable_rate": {
            "executable_action_items": executable_actions,
            "total_action_items": total_actions,
            "rate": quality_rate(executable_actions, total_actions),
            "target": 0.80,
        },
        "history_reuse_hit_rate": {
            "hit_tasks": reuse_hits,
            "total_tasks": total_tasks,
            "rate": quality_rate(reuse_hits, total_tasks),
            "target": 0.40,
        },
        "tasks": task_summaries,
    }


def format_percent(value: float) -> str:
    """Format a 0..1 metric as a percentage."""
    return f"{value * 100:.1f}%"


def run_quality_dashboard(base_dir: Path, format_type: str = "text") -> int:
    """Show Phase 3 quality metrics dashboard."""
    states = load_all_discussion_states(base_dir)
    dashboard = aggregate_quality_metrics(states)

    if format_type == "json":
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))
        return 0

    citation = dashboard["citation_rate"]
    actions = dashboard["action_item_executable_rate"]
    reuse = dashboard["history_reuse_hit_rate"]

    print("📊 Consensus Quality Dashboard")
    print(f"   Tasks: {dashboard['total_tasks']}")
    print(
        "   Citation rate: "
        f"{format_percent(citation['rate'])} "
        f"({citation['cited_responses']}/{citation['total_responses']}, target {format_percent(citation['target'])})"
    )
    print(
        "   Action item executable rate: "
        f"{format_percent(actions['rate'])} "
        f"({actions['executable_action_items']}/{actions['total_action_items']}, target {format_percent(actions['target'])})"
    )
    print(
        "   History consensus reuse hit rate: "
        f"{format_percent(reuse['rate'])} "
        f"({reuse['hit_tasks']}/{reuse['total_tasks']}, target {format_percent(reuse['target'])})"
    )

    if dashboard["tasks"]:
        print("\nRecent tasks:")
        for task in dashboard["tasks"][-5:]:
            metrics = task["metrics"]
            print(
                f"   {task['task_id']}: "
                f"cite {format_percent(metrics['citation_rate']['rate'])}, "
                f"actions {format_percent(metrics['action_item_executable_rate']['rate'])}, "
                f"reuse {'hit' if metrics['history_reuse_hit_rate']['hit'] else 'miss'}"
            )
    return 0


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
    state_dir = base_dir / ".collab" / "state"

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

    metrics = task_state.get("quality_metrics") or calculate_quality_metrics(task_state)
    citation = metrics["citation_rate"]
    actions = metrics["action_item_executable_rate"]
    reuse = metrics["history_reuse_hit_rate"]
    print(f"   Citation rate: {format_percent(citation['rate'])}")
    print(f"   Action executable rate: {format_percent(actions['rate'])}")
    print(f"   History reuse: {'hit' if reuse['hit'] else 'miss'}")

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
    task_state = attach_quality_metrics(task_state)

    # Save state
    save_result = save_consensus_to_agentmemory(base_dir, task_id, task_state)
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
    if save_result.get("saved"):
        print("🧠 Saved consensus to agentmemory")
    elif save_result.get("error"):
        print(f"⚠️  agentmemory save skipped: {save_result['error']}")
    return 0


def run_resume(
    base_dir: Path,
    task_id: str,
    retry_failed: bool = False,
    consensus_scope: Optional[str] = None,
) -> int:
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
    return run_discussion(
        base_dir,
        task_id,
        topic,
        participants,
        max_rounds=resume_max_rounds,
        hard_max_rounds=resume_hard_max_rounds,
        timeout_sec=180,
        resume=True,
        consensus_scope=consensus_scope,
    )


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
    mode: str = "full",
    consensus_scope: Optional[str] = None,
) -> int:
    """Run multi-round discussion until consensus or max rounds.

    mode: 'full' (default) - multi-round persistent, requires init
          'fast' - single-round stateless, no init required (ccg-style)
    """
    discussion_start = time.time()
    collab_dir = base_dir / ".collab"

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
    requested_scope = normalize_consensus_scope(consensus_scope) if consensus_scope else None
    task_state = load_task_state(base_dir, task_id)
    if task_state is None:
        task_state = init_task_state(base_dir, task_id, topic, participants, max_rounds, hard_max_rounds)
        if requested_scope:
            task_state.setdefault("agentmemory", {})["requested_scope"] = requested_scope
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
        if requested_scope:
            task_state.setdefault("agentmemory", {})["requested_scope"] = requested_scope

    agentmemory_state = task_state.setdefault("agentmemory", {})
    active_scope = requested_scope or agentmemory_state.get("requested_scope")
    if active_scope:
        agentmemory_state["requested_scope"] = active_scope

    if not resume and not agentmemory_state.get("recall_attempted"):
        recall_result = recall_related_consensus(base_dir, topic, requested_scope=active_scope)
        agentmemory_state.update({
            "recall_attempted": True,
            "recall_enabled": recall_result.get("enabled", False),
            "recall_projects": recall_result.get("projects", []),
            "related_consensus": recall_result.get("related_consensus", []),
            "expired_consensus": recall_result.get("expired_consensus", []),
            "potential_conflicts": recall_result.get("potential_conflicts", []),
            "recall_error": recall_result.get("error"),
        })
        save_task_state(base_dir, task_id, task_state)
        if agentmemory_state["related_consensus"]:
            print(f"🧠 Recalled {len(agentmemory_state['related_consensus'])} related consensus item(s) from agentmemory")
            if agentmemory_state.get("potential_conflicts"):
                print(f"⚠️  Detected {len(agentmemory_state['potential_conflicts'])} potential historical consensus conflict(s)")
        elif agentmemory_state.get("recall_error"):
            print(f"⚠️  agentmemory recall skipped: {agentmemory_state['recall_error']}")
        else:
            print("🧠 No related agentmemory consensus found")

    # Read current state
    events = read_events(collab_dir / "events.jsonl")
    state = read_state(collab_dir / "state.json")

    print(f"💬 Topic: {topic}")
    print(f"👥 Participants: {', '.join(participants)}")
    print()

    artifacts_refs = []
    timing_log = []
    last_consensus_detail = {
        "consensus": False,
        "blocking_issues": [],
        "dissent": None,
        "agreeing_agents": [],
        "dissenting_agents": [],
        "evidence": [],
        "action_items": [],
    }

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

    task_state = ensure_pre_discuss(base_dir, task_id, topic, task_state, artifacts_refs)
    if task_state.get("pre_discuss") and not task_state.get("pre_discuss_event_logged"):
        append_event(
            base_dir,
            "discussion_message",
            "claude",
            task_id,
            "Pre-discuss initial analysis prepared",
            artifacts=[task_state["pre_discuss"].get("artifact")],
            details={
                "stage": "pre_discuss",
                "response_id": task_state["pre_discuss"].get("response_id"),
            }
        )
        task_state["pre_discuss_event_logged"] = True
        save_task_state(base_dir, task_id, task_state)

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
        protocol_context = collect_protocol_context(task_state, task_id)

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
                base_dir,
                task_id,
                round_num,
                topic,
                history,
                artifacts_refs,
                previous_responses=protocol_context["previous_responses"],
                open_questions=protocol_context["open_questions"],
                targeted_challenges=protocol_context["targeted_challenges"],
                pre_discuss=task_state.get("pre_discuss"),
                related_consensus=task_state.get("agentmemory", {}).get("related_consensus", []),
                potential_conflicts=task_state.get("agentmemory", {}).get("potential_conflicts", []),
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

                    # Codex (API) and Gemini (plan mode) cannot read files themselves.
                    # Inline the context file content instead of passing the path.
                    agent_topic = topic
                    agent_context_file = context_file
                    if context_file and Path(context_file).exists():
                        agent_context_file = None
                        agent_topic = Path(context_file).read_text()

                    prompt = build_discussion_prompt(
                        agent_topic,
                        task_id,
                        agent,
                        round_num,
                        history,
                        artifacts_refs,
                        agent_context_file,
                        previous_responses=protocol_context["previous_responses"],
                        open_questions=protocol_context["open_questions"],
                        targeted_challenges=protocol_context["targeted_challenges"],
                        related_consensus=task_state.get("agentmemory", {}).get("related_consensus", []),
                        potential_conflicts=task_state.get("agentmemory", {}).get("potential_conflicts", []),
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
                    if isinstance(reply.parsed, dict):
                        reply.parsed = normalize_parsed_response(reply.parsed, task_id, round_num, agent)

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
            last_consensus_detail = {
                "consensus": False,
                "blocking_issues": blocking,
                "dissent": "Not all required participants completed successfully.",
                "agreeing_agents": [],
                "dissenting_agents": [
                    p for p in participants
                    if p != "claude" and p not in [reply.agent for reply in replies]
                ],
                "evidence": [],
                "action_items": [],
            }
        else:
            # Judge consensus
            last_consensus_detail = check_consensus(replies)
            consensus = last_consensus_detail["consensus"]
            blocking = last_consensus_detail["blocking_issues"]

        # Mark round as completed
        task_state = complete_round(task_state, round_num, consensus, blocking,
                                   actual_responded=len(replies),
                                   expected_count=expected_participant_count)
        task_state["rounds"][round_num - 1]["consensus_check"].update({
            "dissent": last_consensus_detail.get("dissent"),
            "agreeing_agents": last_consensus_detail.get("agreeing_agents", []),
            "dissenting_agents": last_consensus_detail.get("dissenting_agents", []),
            "evidence": last_consensus_detail.get("evidence", []),
            "action_items": last_consensus_detail.get("action_items", []),
        })
        task_state = attach_quality_metrics(task_state)
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
                'round': round_num,
                'dissent': last_consensus_detail.get("dissent"),
                'evidence': last_consensus_detail.get("evidence", []),
                'action_items': last_consensus_detail.get("action_items", []),
                'blocking_issues': blocking,
            }
            task_state['completed_at'] = datetime.now(timezone.utc).isoformat()
            task_state = attach_quality_metrics(task_state)
            save_task_state(base_dir, task_id, task_state)

            # Save consensus contract for execution phase
            save_consensus_contract(base_dir, task_id, task_state)
            save_result = save_consensus_to_agentmemory(base_dir, task_id, task_state, requested_scope=active_scope)
            save_task_state(base_dir, task_id, task_state)

            # Append discussion_concluded event
            append_event(
                base_dir,
                'discussion_concluded',
                'system',
                task_id,
                f"Consensus reached in round {round_num}",
                details={
                    'consensus': True,
                    'decision': final_decision,
                    'dissent': last_consensus_detail.get("dissent"),
                    'agentmemory_saved': save_result.get("saved", False),
                }
            )

            print(f"\n✅ Consensus reached in round {round_num}!")
            if save_result.get("saved"):
                print("🧠 Saved consensus to agentmemory")
            elif save_result.get("error"):
                print(f"⚠️  agentmemory save skipped: {save_result['error']}")
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
            'decision': '',
            'dissent': last_consensus_detail.get("dissent"),
            'blocking_issues': last_consensus_detail.get("blocking_issues", []),
        }
        task_state['completed_at'] = datetime.now(timezone.utc).isoformat()
        task_state = attach_quality_metrics(task_state)
        save_task_state(base_dir, task_id, task_state)

        append_event(
            base_dir,
            'discussion_concluded',
            'system',
            task_id,
            f"Discussion stopped: hard limit ({hard_max_rounds} rounds) reached",
            details={
                'consensus': False,
                'reason': 'hard_round_limit_reached',
                'dissent': last_consensus_detail.get("dissent"),
            }
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
    discuss_parser.add_argument(
        "--scope",
        choices=["project-specific", "cross-project", "global"],
        help="Override consensus memory scope",
    )

    # History subcommand
    history_parser = subparsers.add_parser("history", help="Show discussion history")
    history_parser.add_argument("task_id", help="Task ID")
    history_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    history_parser.add_argument("--summary", action="store_true", help="Show summary only")

    # Resume subcommand
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted discussion")
    resume_parser.add_argument("task_id", help="Task ID")
    resume_parser.add_argument("--retry-failed", action="store_true", help="Retry failed participants")
    resume_parser.add_argument(
        "--scope",
        choices=["project-specific", "cross-project", "global"],
        help="Override consensus memory scope",
    )

    # Status subcommand
    status_parser = subparsers.add_parser("status", help="Show task status")
    status_parser.add_argument("task_id", help="Task ID")

    # Conclude subcommand
    conclude_parser = subparsers.add_parser("conclude", help="Manually conclude discussion with decision")
    conclude_parser.add_argument("task_id", help="Task ID")
    conclude_parser.add_argument("decision", help="Final decision text")

    # Scan subcommand
    subparsers.add_parser("scan", help="Scan for incomplete tasks")

    # Dashboard subcommand
    dashboard_parser = subparsers.add_parser("dashboard", help="Show consensus quality metrics dashboard")
    dashboard_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

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

            collab_dir = intended_base / ".collab"

            # Auto-init if missing at intended location (silent if already exists)
            if not collab_dir.exists():
                init_collaboration(str(intended_base), source="auto")
                print(f"✓ Initialized collaboration at: {collab_dir}")

            base = intended_base
        else:
            base = resolve_existing_base_dir(args.base_dir)

        if args.command == "scan":
            sys.exit(run_scan(base))
        elif args.command == "dashboard":
            sys.exit(run_quality_dashboard(base, args.format))
        elif args.command == "history":
            sys.exit(run_history(base, args.task_id, args.format, args.summary))
        elif args.command == "status":
            sys.exit(run_status(base, args.task_id))
        elif args.command == "conclude":
            sys.exit(run_conclude(base, args.task_id, args.decision))
        elif args.command == "resume":
            sys.exit(run_resume(base, args.task_id, args.retry_failed, consensus_scope=args.scope))
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

            # Detect tmux availability for status display
            use_tmux_env = os.environ.get("CCG_USE_TMUX", "").lower()
            if use_tmux_env == "false":
                use_tmux = False
                tmux_info = None
            else:
                tmux_info = get_tmux_info()
                use_tmux = tmux_info['available']

            # Display runtime status before starting discussion
            show_runtime_status(str(base), task_id=task_id, topic=topic,
                              participants=participants, mode=args.mode,
                              max_rounds=args.max_rounds,
                              use_tmux=use_tmux,
                              tmux_version=tmux_info.get('version') if tmux_info else None)
            sys.stdout.flush()  # Force output before run_discussion starts

            sys.exit(run_discussion(base, task_id, topic, participants,
                                   args.max_rounds, hard_max_rounds=10,
                                   timeout_sec=args.timeout_sec, mode=args.mode,
                                   consensus_scope=args.scope))
        else:
            parser.print_help()
            sys.exit(1)

    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
