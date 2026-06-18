from infravox_reviewer.demo_ui import (
    aggregate_reports,
    build_review_payload,
    category_counts,
    findings_table_html,
    findings_table_rows,
    load_diff_choices,
    severity_counts,
)


def test_load_diff_choices_discovers_assignment_diffs():
    choices = load_diff_choices()

    assert [choice.filename for choice in choices] == [
        "diff1_python.txt",
        "diff2_javascript.txt",
        "diff3_typescript.txt",
    ]
    assert [choice.language for choice in choices] == ["python", "javascript", "typescript"]
    assert choices[0].label == "Diff 1 - Python"


def test_build_review_payload_uses_selected_diff_and_context():
    choice = load_diff_choices()[1]

    payload = build_review_payload(choice=choice, context="Demo context")

    assert payload["language"] == "javascript"
    assert payload["context"] == "Demo context"
    assert "async function getUsers" in payload["diff"]


def test_findings_table_rows_match_assignment_columns():
    report = {
        "findings": [
            {
                "id": "F-001",
                "line": 7,
                "category": "security",
                "severity": "critical",
                "title": "Dynamic SQL construction can allow injection",
                "description": "Runtime values are interpolated into SQL.",
                "suggestion": "Use parameterized queries.",
            }
        ]
    }

    rows = findings_table_rows(report)

    assert rows == [
        {
            "ID": "F-001",
            "Line": 7,
            "Category": "security",
            "Severity": "critical",
            "Title": "Dynamic SQL construction can allow injection",
            "Description": "Runtime values are interpolated into SQL.",
            "Suggestion": "Use parameterized queries.",
        }
    ]


def test_findings_table_html_colors_and_escapes_values():
    report = {
        "findings": [
            {
                "id": "F-001",
                "line": 7,
                "category": "security",
                "severity": "critical",
                "title": "<script>alert('x')</script>",
                "description": "Runtime values are interpolated into SQL.",
                "suggestion": "Use parameterized queries.",
            }
        ]
    }

    html = findings_table_html(report)

    assert "findings-table" in html
    assert "chip category-security" in html
    assert "chip severity-critical" in html
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html
    assert "<script>" not in html


def test_report_count_helpers_are_stable_for_empty_and_populated_reports():
    empty_report = {"findings": []}
    report = {
        "findings": [
            {"category": "security", "severity": "critical"},
            {"category": "security", "severity": "high"},
            {"category": "performance", "severity": "high"},
        ]
    }

    assert category_counts(empty_report) == {}
    assert severity_counts(empty_report) == {}
    assert category_counts(report) == {"performance": 1, "security": 2}
    assert severity_counts(report) == {"critical": 1, "high": 2}


def test_aggregate_reports_summarizes_multiple_diff_outputs():
    reports = {
        "Diff 1 - Python": {
            "overall_severity": "critical",
            "verdict": "request_changes",
            "findings": [
                {"category": "security", "severity": "critical"},
                {"category": "correctness", "severity": "high"},
            ],
            "processing_time_ms": 4,
        },
        "Diff 2 - Javascript": {
            "overall_severity": "high",
            "verdict": "request_changes",
            "findings": [
                {"category": "performance", "severity": "high"},
            ],
            "processing_time_ms": 3,
        },
    }

    summary = aggregate_reports(reports)

    assert summary["diff_count"] == 2
    assert summary["total_findings"] == 3
    assert summary["processing_time_ms"] == 7
    assert summary["overall_severity"] == "critical"
    assert summary["verdict"] == "request_changes"
    assert summary["category_counts"] == {"correctness": 1, "performance": 1, "security": 1}
    assert summary["severity_counts"] == {"critical": 1, "high": 2}
