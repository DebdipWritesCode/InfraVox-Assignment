from pathlib import Path

from fastapi.testclient import TestClient

from infravox_reviewer.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def test_review_endpoint_generates_and_stores_report():
    client = TestClient(app)

    response = client.post(
        "/review",
        json={
            "diff": (FIXTURES / "diff1_python.txt").read_text(),
            "language": "python",
            "context": "Add refund endpoint",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "review_id" not in payload
    assert "report" not in payload
    assert payload["verdict"] == "request_changes"
    assert payload["overall_severity"] == "critical"
    assert {
        "pr_summary",
        "verdict",
        "verdict_reason",
        "overall_severity",
        "findings",
        "positive_observations",
        "missing_tests",
        "agent_findings_count",
        "processing_time_ms",
    } == set(payload)

    review_id = response.headers["x-review-id"]
    stored = client.get(f"/review/{review_id}")
    assert stored.status_code == 200
    assert stored.json()["review_id"] == review_id


def test_reviews_endpoint_lists_generated_reviews():
    client = TestClient(app)
    client.post(
        "/review",
        json={"diff": (FIXTURES / "diff2_javascript.txt").read_text(), "language": "javascript"},
    )

    response = client.get("/reviews")

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert {"review_id", "pr_summary", "verdict", "overall_severity", "created_at"} <= set(
        response.json()[0]
    )


def test_health_endpoint_reports_configured_groq_status_without_requiring_key():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["groq"]["configured"] in {True, False}
