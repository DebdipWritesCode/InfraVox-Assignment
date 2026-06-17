from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Category(str, Enum):
    security = "security"
    performance = "performance"
    correctness = "correctness"
    style = "style"
    test_coverage = "test_coverage"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    clean = "clean"


class Verdict(str, Enum):
    approve = "approve"
    request_changes = "request_changes"
    needs_discussion = "needs_discussion"


class ReviewRequest(BaseModel):
    diff: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    context: str | None = None


class DiffLine(BaseModel):
    number: int
    content: str
    file_path: str | None = None


class Finding(BaseModel):
    id: str = ""
    line: int
    line_content: str
    category: Category
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    description: str
    suggestion: str


class ReviewReport(BaseModel):
    pr_summary: str
    verdict: Verdict
    verdict_reason: str
    overall_severity: Severity
    findings: list[Finding]
    positive_observations: list[str]
    missing_tests: list[str]
    agent_findings_count: dict[str, int]
    processing_time_ms: int


class StoredReviewSummary(BaseModel):
    review_id: str
    pr_summary: str
    verdict: Verdict
    overall_severity: Severity
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoredReview(BaseModel):
    review_id: str
    created_at: datetime
    request: ReviewRequest
    report: ReviewReport
