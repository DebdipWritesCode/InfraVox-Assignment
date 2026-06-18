from pathlib import Path

import infravox_reviewer.graph as graph_module
from infravox_reviewer.graph import run_review_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_returns_assignment_schema_and_request_changes_verdict():
    report = run_review_pipeline(
        diff=(FIXTURES / "diff1_python.txt").read_text(),
        language="python",
        context="Add refund endpoint and fix transaction lookup",
    )

    assert report.pr_summary
    assert report.verdict == "request_changes"
    assert report.overall_severity == "critical"
    assert report.processing_time_ms >= 0
    assert report.findings[0].id == "F-001"
    assert len(report.positive_observations) >= 2
    assert report.agent_findings_count["security"] >= 3


def test_pipeline_deduplicates_and_numbers_findings_stably():
    report = run_review_pipeline(
        diff=(FIXTURES / "diff3_typescript.txt").read_text(),
        language="typescript",
        context=None,
    )

    ids = [finding.id for finding in report.findings]

    assert ids == [f"F-{index:03d}" for index in range(1, len(ids) + 1)]
    assert len({(finding.line, finding.category, finding.title) for finding in report.findings}) == len(
        report.findings
    )
    assert (
        "Add tests for repeated or invalid state transitions and side-effect failure handling."
        in report.missing_tests
    )


def test_pipeline_preserves_assignment_issue_class_coverage():
    expected_categories = {
        ("diff1_python.txt", "python"): {"security", "correctness"},
        ("diff2_javascript.txt", "javascript"): {"security", "performance", "correctness"},
        ("diff3_typescript.txt", "typescript"): {
            "security",
            "performance",
            "correctness",
            "style",
            "test_coverage",
        },
    }

    for (fixture_name, language), categories in expected_categories.items():
        report = run_review_pipeline(
            diff=(FIXTURES / fixture_name).read_text(),
            language=language,
            context=None,
        )

        assert categories <= {finding.category.value for finding in report.findings}
        assert report.verdict == "request_changes"


def test_pipeline_invokes_each_specialist_ai_reviewer(monkeypatch):
    calls = []

    def fake_ai_specialist_reviewer(
        *,
        agent_name,
        category,
        responsibility,
        diff,
        language,
        context,
        lines,
        fallback_findings,
    ):
        calls.append(
            {
                "agent_name": agent_name,
                "category": category,
                "responsibility": responsibility,
                "diff": diff,
                "language": language,
                "context": context,
                "line_count": len(lines),
                "fallback_count": len(fallback_findings),
            }
        )
        return fallback_findings

    monkeypatch.setattr(
        graph_module,
        "ai_specialist_reviewer",
        fake_ai_specialist_reviewer,
        raising=False,
    )

    report = graph_module.run_review_pipeline(
        diff=(FIXTURES / "diff1_python.txt").read_text(),
        language="python",
        context="Add refund endpoint",
    )

    assert sorted(call["agent_name"] for call in calls) == [
        "correctness_reviewer",
        "performance_reviewer",
        "security_reviewer",
        "style_reviewer",
        "test_coverage_reviewer",
    ]
    assert {call["category"] for call in calls} == {
        "security",
        "performance",
        "correctness",
        "style",
        "test_coverage",
    }
    assert all(call["diff"] == (FIXTURES / "diff1_python.txt").read_text() for call in calls)
    assert all(call["language"] == "python" for call in calls)
    assert all(call["context"] == "Add refund endpoint" for call in calls)
    assert all(call["line_count"] > 0 for call in calls)
    assert sum(call["fallback_count"] for call in calls) == len(report.findings)
