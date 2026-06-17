from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from .graph import run_review_pipeline
from .llm import check_groq_connectivity
from .models import ReviewReport, ReviewRequest, StoredReview, StoredReviewSummary
from .store import ReviewStore


store = ReviewStore()


def create_app() -> FastAPI:
    app = FastAPI(
        title="InfraVox AI Code Reviewer",
        version="0.1.0",
        description="Assignment A FastAPI service powered by a LangGraph review pipeline.",
    )

    @app.post("/review", response_model=ReviewReport)
    def create_review(request: ReviewRequest, response: Response) -> ReviewReport:
        report = run_review_pipeline(
            diff=request.diff,
            language=request.language,
            context=request.context,
        )
        stored = store.create(request, report)
        response.headers["X-Review-ID"] = stored.review_id
        return report

    @app.get("/review/{review_id}", response_model=StoredReview)
    def get_review(review_id: str) -> StoredReview:
        stored = store.get(review_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Review not found")
        return stored

    @app.get("/reviews", response_model=list[StoredReviewSummary])
    def list_reviews() -> list[StoredReviewSummary]:
        return store.list()

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "groq": await check_groq_connectivity(),
        }

    return app


app = create_app()
