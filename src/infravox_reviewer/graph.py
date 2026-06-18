from __future__ import annotations

import contextlib
import io
import time
from typing import TypedDict

import warnings

from .diff_parser import extract_added_lines
from .llm_review import ai_specialist_reviewer
from .models import Category, DiffLine, Finding, ReviewReport, Severity, Verdict
from .reviewers import (
    correctness_reviewer,
    performance_reviewer,
    security_reviewer,
    style_reviewer,
    test_coverage_reviewer,
)


class ReviewState(TypedDict, total=False):
    diff: str
    language: str
    context: str | None
    started_at: float
    lines: list[DiffLine]
    security_findings: list[Finding]
    performance_findings: list[Finding]
    correctness_findings: list[Finding]
    style_findings: list[Finding]
    test_coverage_findings: list[Finding]
    report: ReviewReport


REVIEWER_KEYS = {
    Category.security.value: "security_findings",
    Category.performance.value: "performance_findings",
    Category.correctness.value: "correctness_findings",
    Category.style.value: "style_findings",
    Category.test_coverage.value: "test_coverage_findings",
}

SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

AGENT_RESPONSIBILITIES = {
    Category.security.value: (
        "Find security vulnerabilities: SQL injection, hardcoded credentials, unsafe "
        "deserialization, unvalidated inputs, IDOR risks, exposed secrets. For each finding, "
        "produce a line number, a plain-English description of the vulnerability, and why it "
        "is exploitable. Be paranoid."
    ),
    Category.performance.value: (
        "Find performance issues: N+1 queries, missing indexes implied by query patterns, "
        "unnecessary loops over large collections, synchronous calls that should be async, "
        "memory leaks, and repeated expensive operations that should be cached. Focus on "
        "issues that hurt at scale, not micro-optimizations."
    ),
    Category.correctness.value: (
        "Find logical bugs and edge cases: missing null or undefined checks, off-by-one "
        "errors, incorrect error handling, race conditions, missing input validation, and "
        "incorrect boolean logic. Focus on bugs that can cause production failures."
    ),
    Category.style.value: (
        "Find code quality issues: functions that are too long and should be split, unclear "
        "variable names, missing or incorrect docstrings, dead code, magic numbers, and "
        "duplicated logic that should be extracted. Only flag issues that genuinely hurt "
        "readability or maintainability."
    ),
    Category.test_coverage.value: (
        "Analyse what the diff adds or changes and identify what is not tested: new code "
        "paths with no corresponding test, edge cases existing tests miss, error paths that "
        "are not covered, and mocked dependencies that mask real integration issues. Output "
        "specific suggestions for tests that should be written."
    ),
}


def _parse_diff_node(state: ReviewState) -> ReviewState:
    return {"lines": extract_added_lines(state["diff"])}


def _security_node(state: ReviewState) -> ReviewState:
    fallback_findings = security_reviewer(state["lines"], state["language"])
    return {
        "security_findings": ai_specialist_reviewer(
            agent_name="security_reviewer",
            category=Category.security.value,
            responsibility=AGENT_RESPONSIBILITIES[Category.security.value],
            diff=state["diff"],
            language=state["language"],
            context=state.get("context"),
            lines=state["lines"],
            fallback_findings=fallback_findings,
        )
    }


def _performance_node(state: ReviewState) -> ReviewState:
    fallback_findings = performance_reviewer(state["lines"], state["language"])
    return {
        "performance_findings": ai_specialist_reviewer(
            agent_name="performance_reviewer",
            category=Category.performance.value,
            responsibility=AGENT_RESPONSIBILITIES[Category.performance.value],
            diff=state["diff"],
            language=state["language"],
            context=state.get("context"),
            lines=state["lines"],
            fallback_findings=fallback_findings,
        )
    }


def _correctness_node(state: ReviewState) -> ReviewState:
    fallback_findings = correctness_reviewer(state["lines"], state["language"])
    return {
        "correctness_findings": ai_specialist_reviewer(
            agent_name="correctness_reviewer",
            category=Category.correctness.value,
            responsibility=AGENT_RESPONSIBILITIES[Category.correctness.value],
            diff=state["diff"],
            language=state["language"],
            context=state.get("context"),
            lines=state["lines"],
            fallback_findings=fallback_findings,
        )
    }


def _style_node(state: ReviewState) -> ReviewState:
    fallback_findings = style_reviewer(state["lines"], state["language"])
    return {
        "style_findings": ai_specialist_reviewer(
            agent_name="style_reviewer",
            category=Category.style.value,
            responsibility=AGENT_RESPONSIBILITIES[Category.style.value],
            diff=state["diff"],
            language=state["language"],
            context=state.get("context"),
            lines=state["lines"],
            fallback_findings=fallback_findings,
        )
    }


def _test_coverage_node(state: ReviewState) -> ReviewState:
    fallback_findings = test_coverage_reviewer(state["lines"], state["language"])
    return {
        "test_coverage_findings": ai_specialist_reviewer(
            agent_name="test_coverage_reviewer",
            category=Category.test_coverage.value,
            responsibility=AGENT_RESPONSIBILITIES[Category.test_coverage.value],
            diff=state["diff"],
            language=state["language"],
            context=state.get("context"),
            lines=state["lines"],
            fallback_findings=fallback_findings,
        )
    }


def _baseline_findings(state: ReviewState) -> list[Finding]:
    all_findings: list[Finding] = []
    for key in REVIEWER_KEYS.values():
        all_findings.extend(state.get(key, []))
    return all_findings


def _summarize_pr(diff: str, language: str, context: str | None) -> str:
    if context:
        return context.rstrip(".") + "."

    for raw_line in diff.splitlines():
        if "PR:" in raw_line:
            return raw_line.split("PR:", 1)[1].strip().rstrip(".") + "."

    return f"Review of a {language.lower()} pull request diff."


def _positive_observations(language: str) -> list[str]:
    return [
        f"The diff is small enough for a focused {language.lower()} line-level review.",
        "The changes are organized around clear functions, which makes targeted fixes straightforward.",
    ]


def _deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    deduped: list[Finding] = []
    seen: set[tuple[int, str, str]] = set()
    for finding in findings:
        key = (finding.line, finding.category.value, finding.title.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda finding: (
            SEVERITY_RANK[finding.severity],
            finding.line,
            finding.category.value,
            finding.title,
        ),
    )


def _overall_severity(findings: list[Finding]) -> Severity:
    if not findings:
        return Severity.clean
    highest = min(findings, key=lambda finding: SEVERITY_RANK[finding.severity]).severity
    return Severity(highest)


def _verdict_for_severity(overall_severity: Severity) -> tuple[Verdict, str]:
    if overall_severity in {Severity.critical, Severity.high}:
        return (
            Verdict.request_changes,
            "The diff contains high-risk findings that should be fixed before merge.",
        )
    if overall_severity is Severity.medium:
        return (
            Verdict.needs_discussion,
            "The diff has medium-risk issues that need reviewer discussion before approval.",
        )
    return (
        Verdict.approve,
        "No blocking issues were found by the automated review pipeline.",
    )


def _merge_findings_node(state: ReviewState) -> ReviewState:
    all_findings = _baseline_findings(state)

    findings = _sort_findings(_deduplicate_findings(all_findings))
    numbered_findings = [
        finding.model_copy(update={"id": f"F-{index:03d}"})
        for index, finding in enumerate(findings, start=1)
    ]

    overall_severity = _overall_severity(numbered_findings)
    verdict, verdict_reason = _verdict_for_severity(overall_severity)
    missing_tests = [
        finding.suggestion
        for finding in numbered_findings
        if finding.category is Category.test_coverage
    ]
    processing_time_ms = int((time.perf_counter() - state["started_at"]) * 1000)

    report = ReviewReport(
        pr_summary=_summarize_pr(state["diff"], state["language"], state.get("context")),
        verdict=verdict,
        verdict_reason=verdict_reason,
        overall_severity=overall_severity,
        findings=numbered_findings,
        positive_observations=_positive_observations(state["language"]),
        missing_tests=missing_tests,
        agent_findings_count={
            category: len(
                [
                    finding
                    for finding in numbered_findings
                    if finding.category.value == category
                ]
            )
            for category in REVIEWER_KEYS
        },
        processing_time_ms=processing_time_ms,
    )
    return {"report": report}


def build_review_graph():
    with contextlib.redirect_stderr(io.StringIO()):
        from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(ReviewState)
    workflow.add_node("parse_diff", _parse_diff_node)
    workflow.add_node("security_reviewer", _security_node)
    workflow.add_node("performance_reviewer", _performance_node)
    workflow.add_node("correctness_reviewer", _correctness_node)
    workflow.add_node("style_reviewer", _style_node)
    workflow.add_node("test_coverage_reviewer", _test_coverage_node)
    workflow.add_node("merge_findings", _merge_findings_node)

    workflow.add_edge(START, "parse_diff")
    workflow.add_edge("parse_diff", "security_reviewer")
    workflow.add_edge("parse_diff", "performance_reviewer")
    workflow.add_edge("parse_diff", "correctness_reviewer")
    workflow.add_edge("parse_diff", "style_reviewer")
    workflow.add_edge("parse_diff", "test_coverage_reviewer")
    workflow.add_edge(
        [
            "security_reviewer",
            "performance_reviewer",
            "correctness_reviewer",
            "style_reviewer",
            "test_coverage_reviewer",
        ],
        "merge_findings",
    )
    workflow.add_edge("merge_findings", END)
    return workflow.compile()


_warning_filters = warnings.filters[:]
warnings.simplefilter("ignore")
try:
    REVIEW_GRAPH = build_review_graph()
finally:
    warnings.filters[:] = _warning_filters


def run_review_pipeline(diff: str, language: str, context: str | None = None) -> ReviewReport:
    result = REVIEW_GRAPH.invoke(
        {
            "diff": diff,
            "language": language,
            "context": context,
            "started_at": time.perf_counter(),
        }
    )
    return result["report"]
