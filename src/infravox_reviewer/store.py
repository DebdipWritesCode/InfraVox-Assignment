from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import ReviewReport, ReviewRequest, StoredReview, StoredReviewSummary


class ReviewStore:
    def __init__(self) -> None:
        self._reviews: dict[str, StoredReview] = {}

    def create(self, request: ReviewRequest, report: ReviewReport) -> StoredReview:
        review_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        stored = StoredReview(
            review_id=review_id,
            created_at=created_at,
            request=request,
            report=report,
        )
        self._reviews[review_id] = stored
        return stored

    def get(self, review_id: str) -> StoredReview | None:
        return self._reviews.get(review_id)

    def list(self) -> list[StoredReviewSummary]:
        return [
            StoredReviewSummary(
                review_id=stored.review_id,
                pr_summary=stored.report.pr_summary,
                verdict=stored.report.verdict,
                overall_severity=stored.report.overall_severity,
                created_at=stored.created_at,
            )
            for stored in sorted(
                self._reviews.values(),
                key=lambda review: review.created_at,
                reverse=True,
            )
        ]
