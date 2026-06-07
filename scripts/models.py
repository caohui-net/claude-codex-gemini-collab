#!/usr/bin/env python3
"""Structured data models for collab discussion sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActionItem:
    """Executable work item produced by a discussion conclusion."""

    owner: str
    task: str
    due: Optional[str] = None
    verification: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Challenge:
    """A targeted challenge against a prior response."""

    target_agent: str
    target_response_id: str
    question: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Response:
    """A structured participant response in a discussion round."""

    id: str
    agent: str
    content: str
    previous_responses: List[str] = field(default_factory=list)
    targeted_challenges: List[Challenge] = field(default_factory=list)
    consensus: Optional[bool] = None
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    blocking_issues: List[str] = field(default_factory=list)
    dissent: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Round:
    """One discussion round and its unresolved questions."""

    number: int
    responses: List[Response] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Conclusion:
    """Final discussion conclusion, including dissent when present."""

    decision: str
    dissent: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscussionSession:
    """Top-level structured discussion session."""

    id: str
    topic: str
    participants: List[str]
    rounds: List[Round] = field(default_factory=list)
    conclusion: Optional[Conclusion] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConsensusArtifact:
    """Structured consensus artifact persisted to agentmemory."""

    topic: str
    participants: List[str]
    decision: str
    dissent: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    project_scope: str = "project-specific"
    confidence: float = 0.0
    supersedes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    task_id: Optional[str] = None
    round: Optional[int] = None
    created_at: Optional[str] = None
    namespace: Optional[str] = None
    permission: Dict[str, Any] = field(default_factory=dict)
    ttl_days: Optional[int] = None
    expires_at: Optional[str] = None
    version: int = 1
    previous_version_id: Optional[str] = None
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Conflict:
    """Detected contradiction between a new topic and old consensus."""

    old_consensus_id: str
    reason: str
    severity: str
    old_decision: str
    confidence: float = 0.0
    project: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
