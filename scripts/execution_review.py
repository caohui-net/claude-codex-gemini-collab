#!/usr/bin/env python3
"""
Execution review report structure and validation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReviewStatus(Enum):
    """Execution review status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


@dataclass
class ExecutionReviewReport:
    """Structured execution review report."""
    task_id: str
    command: str
    exit_code: int
    changed_files: list[str]
    test_results: Optional[dict] = None
    build_results: Optional[dict] = None
    failure_summary: str = ""
    log_reference: str = ""
    review_status: ReviewStatus = ReviewStatus.APPROVED
    feedback_items: list[str] = None

    def __post_init__(self):
        if self.feedback_items is None:
            self.feedback_items = []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "changed_files": self.changed_files,
            "test_results": self.test_results,
            "build_results": self.build_results,
            "failure_summary": self.failure_summary,
            "log_reference": self.log_reference,
            "review_status": self.review_status.value,
            "feedback_items": self.feedback_items
        }
