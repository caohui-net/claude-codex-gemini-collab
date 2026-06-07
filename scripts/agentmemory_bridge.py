#!/usr/bin/env python3
"""Optional agentmemory bridge for discussion consensus recall/save."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_AGENTMEMORY_WS_URL = "ws://localhost:49134"


class AgentMemoryBridge:
    """Small iii-sdk bridge for agentmemory long-term memory operations.

    Importing this module does not require iii-sdk. The dependency is loaded
    only when a bridge instance is created, so collab remains usable without
    agentmemory installed or running.
    """

    def __init__(self, ws_url: Optional[str] = None):
        self.ws_url = ws_url or os.environ.get("CCG_AGENTMEMORY_WS_URL") or DEFAULT_AGENTMEMORY_WS_URL

        try:
            from iii import register_worker
        except ImportError as exc:
            raise RuntimeError("iii-sdk is not installed") from exc

        self.client = register_worker(self.ws_url)
        connect = getattr(self.client, "connect", None)
        if callable(connect):
            connect()

    def _trigger(self, function_id: str, payload: Dict[str, Any]) -> Any:
        return self.client.trigger({
            "function_id": function_id,
            "payload": payload,
        })

    def recall_consensus(
        self,
        query: str,
        projects: Iterable[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Recall related discussion consensus memories across projects."""
        results: List[Dict[str, Any]] = []
        seen = set()
        per_project_limit = max(1, limit)

        for project in projects:
            payload = {
                "project": project,
                "query": f"discussion_consensus {query}",
                "limit": per_project_limit,
            }
            raw = self._trigger("mem::smart-search", payload)
            for hit in normalize_memory_hits(raw):
                key = str(hit.get("id") or hit.get("memory_id") or hit.get("content") or hit)
                if key in seen:
                    continue
                seen.add(key)
                hit.setdefault("project", project)
                results.append(hit)
                if len(results) >= limit:
                    return results

        return results

    def save_consensus(
        self,
        artifact: Dict[str, Any],
        project: str,
    ) -> Dict[str, Any]:
        """Save a structured consensus artifact as long-term memory."""
        topic = str(artifact.get("topic") or "discussion consensus")
        tags = [str(tag) for tag in artifact.get("tags", []) if str(tag).strip()]
        concepts = dedupe([topic, "discussion_consensus", artifact.get("project_scope"), *tags])
        content = json.dumps(
            {"type": "discussion_consensus", **artifact},
            ensure_ascii=False,
            sort_keys=True,
        )

        payload = {
            "project": project,
            "title": f"Consensus: {topic[:96]}",
            "content": content,
            "concepts": concepts,
        }
        return self._trigger("mem::remember", payload)


def dedupe(items: Iterable[Any]) -> List[str]:
    """Deduplicate truthy string values while preserving order."""
    seen = set()
    result = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_memory_hits(raw: Any) -> List[Dict[str, Any]]:
    """Normalize common agentmemory search result shapes."""
    if raw is None:
        return []

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = (
            raw.get("results")
            or raw.get("hits")
            or raw.get("memories")
            or raw.get("items")
            or raw.get("matches")
            or []
        )
        if isinstance(items, dict):
            items = [items]
    else:
        return []

    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(dict(item))
        else:
            normalized.append({"content": str(item)})
    return normalized
