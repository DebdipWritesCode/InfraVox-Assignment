from __future__ import annotations

from ..models import Category, DiffLine, Finding
from .common import append_unique, finding, is_comment_line


def _has_tests_in_diff(lines: list[DiffLine]) -> bool:
    test_markers = ("test(", "it(", "describe(", "pytest", "unittest")
    return any(any(marker in line.content.lower() for marker in test_markers) for line in lines)


def _state_transition_side_effect_without_tests(lines: list[DiffLine]) -> DiffLine | None:
    if _has_tests_in_diff(lines):
        return None

    mutation_line: DiffLine | None = None
    side_effect_line: DiffLine | None = None
    mutation_terms = (
        "status =",
        ".status =",
        "state =",
        ".state =",
        "update ",
        "delete ",
        "cancel",
        "refund",
        ".save(",
    )
    side_effect_terms = (
        "notification",
        "email",
        ".send(",
        "publish",
        "enqueue",
        "webhook",
        "dispatch",
    )

    for line in lines:
        if is_comment_line(line.content):
            continue
        lowered = line.content.lower()
        if mutation_line is None and any(term in lowered for term in mutation_terms):
            mutation_line = line
        if side_effect_line is None and any(term in lowered for term in side_effect_terms):
            side_effect_line = line

    if mutation_line and side_effect_line:
        return mutation_line
    return None


def test_coverage_reviewer(lines: list[DiffLine], language: str) -> list[Finding]:
    findings: list[Finding] = []

    transition_line = _state_transition_side_effect_without_tests(lines)
    if transition_line:
        append_unique(
            findings,
            finding(
                line=transition_line,
                category=Category.test_coverage,
                severity="medium",
                title="State transition side effects need tests",
                description=(
                    "The diff changes persisted state and triggers an external side effect, but "
                    "does not show tests for repeated transitions or side-effect failure."
                ),
                suggestion=(
                    "Add tests for repeated or invalid state transitions and side-effect "
                    "failure handling."
                ),
            ),
        )

    return findings


test_coverage_reviewer.__test__ = False
