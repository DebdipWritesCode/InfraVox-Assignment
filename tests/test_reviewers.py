from pathlib import Path

from infravox_reviewer.diff_parser import extract_added_lines
from infravox_reviewer.models import Category
from infravox_reviewer.reviewers import (
    correctness_reviewer,
    performance_reviewer,
    security_reviewer,
    style_reviewer,
    test_coverage_reviewer,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _lines(name: str):
    return extract_added_lines((FIXTURES / name).read_text())


def _titles(findings):
    return {finding.title for finding in findings}


def test_security_reviewer_finds_all_planted_security_issues():
    findings = []
    findings.extend(security_reviewer(_lines("diff1_python.txt"), "python"))
    findings.extend(security_reviewer(_lines("diff2_javascript.txt"), "javascript"))
    findings.extend(security_reviewer(_lines("diff3_typescript.txt"), "typescript"))

    titles = _titles(findings)

    assert "Dynamic SQL construction can allow injection" in titles
    assert "Hardcoded secret value" in titles
    assert "Password update stores un-hashed password input" in titles
    assert "Authorization check missing for sensitive operation" in titles
    assert "Unescaped HTML/template interpolation" in titles
    assert all(finding.category is Category.security for finding in findings)


def test_correctness_reviewer_finds_planted_correctness_issues():
    findings = []
    findings.extend(correctness_reviewer(_lines("diff1_python.txt"), "python"))
    findings.extend(correctness_reviewer(_lines("diff2_javascript.txt"), "javascript"))
    findings.extend(correctness_reviewer(_lines("diff3_typescript.txt"), "typescript"))

    titles = _titles(findings)

    assert "Possible null dereference after lookup" in titles
    assert "File opened without context manager" in titles
    assert "Request JSON is used without validation" in titles
    assert "Missing query parameter validation" in titles
    assert "Missing result handling" in titles
    assert "Unknown map key can produce invalid result" in titles


def test_performance_reviewer_finds_planted_scaling_issues():
    findings = []
    findings.extend(performance_reviewer(_lines("diff2_javascript.txt"), "javascript"))
    findings.extend(performance_reviewer(_lines("diff3_typescript.txt"), "typescript"))

    titles = _titles(findings)

    assert "N+1 query in loop" in titles
    assert "Undefined related-record lookup in enrichment" in titles
    assert "Unbounded polling loop" in titles
    assert "Await inside loop serializes independent work" in titles


def test_style_and_test_reviewers_find_generic_findings():
    style_findings = style_reviewer(_lines("diff3_typescript.txt"), "typescript")
    test_findings = test_coverage_reviewer(_lines("diff3_typescript.txt"), "typescript")

    assert "Avoid any for newly added value" in _titles(style_findings)
    assert "State transition side effects need tests" in _titles(test_findings)
