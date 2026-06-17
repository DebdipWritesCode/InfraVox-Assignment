from __future__ import annotations

import re

from ..models import Category, DiffLine, Finding
from .common import append_unique, find_line, finding


def _any_type(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(lines, lambda line: re.search(r":\s*any\b", line.content) is not None)


def style_reviewer(lines: list[DiffLine], language: str) -> list[Finding]:
    findings: list[Finding] = []

    any_line = _any_type(lines)
    if any_line:
        append_unique(
            findings,
            finding(
                line=any_line,
                category=Category.style,
                severity="medium",
                title="Avoid any for newly added value",
                description="The new code uses `any`, which bypasses TypeScript type checking.",
                suggestion="Replace `any` with a specific type, union, or safer unknown shape.",
            ),
        )

    return findings
