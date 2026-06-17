from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from ..models import Category, DiffLine, Finding


SeverityLiteral = Literal["critical", "high", "medium", "low"]
LinePredicate = Callable[[DiffLine], bool]


def find_line(lines: list[DiffLine], predicate: LinePredicate) -> DiffLine | None:
    return next((line for line in lines if predicate(line)), None)


def finding(
    *,
    line: DiffLine | None,
    category: Category,
    severity: SeverityLiteral,
    title: str,
    description: str,
    suggestion: str,
) -> Finding:
    return Finding(
        line=line.number if line else 1,
        line_content=line.content if line else "",
        category=category,
        severity=severity,
        title=title,
        description=description,
        suggestion=suggestion,
    )


def append_unique(findings: list[Finding], finding: Finding) -> None:
    key = (finding.line, finding.category, finding.title)
    if key not in {(item.line, item.category, item.title) for item in findings}:
        findings.append(finding)


def starts_function_scope(content: str) -> bool:
    stripped = content.strip()
    return stripped.startswith(
        (
            "def ",
            "async def ",
            "function ",
            "async function ",
            "export function ",
            "export async function ",
        )
    )


def is_comment_line(content: str) -> bool:
    stripped = content.strip()
    return stripped.startswith(("#", "//"))
