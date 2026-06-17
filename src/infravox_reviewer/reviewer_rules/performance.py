from __future__ import annotations

import re

from ..models import Category, DiffLine, Finding
from .common import append_unique, find_line, finding, starts_function_scope


DECLARATION_RE = re.compile(r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
BRACKET_LOOKUP_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\[[^\]]+\]")


def _loop_has_db_query(lines: list[DiffLine], index: int) -> bool:
    body = " ".join(item.content.lower() for item in lines[index + 1 : index + 5])
    return any(marker in body for marker in ("db.query", "db.execute", "repo.find", "findbyid"))


def _loop_contains_await(lines: list[DiffLine], index: int) -> bool:
    for line in lines[index + 1 : index + 8]:
        stripped = line.content.strip()
        if not stripped:
            continue
        if "await " in stripped:
            return True
        if stripped == "}":
            return False
    return False


def _unbounded_polling_loop(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: line.content.strip().startswith("while ")
        and any(term in line.content.lower() for term in ("pending", "status"))
        and not any(term in line.content.lower() for term in ("timeout", "attempt", "retry")),
    )


def _declared_names(content: str) -> set[str]:
    return {match.group("name") for match in DECLARATION_RE.finditer(content)}


def _inside_recent_map_context(lines: list[DiffLine], index: int) -> bool:
    window = lines[max(0, index - 3) : index + 1]
    return any(".map(" in line.content for line in window)


def _undefined_related_record_lookup(lines: list[DiffLine]) -> DiffLine | None:
    declared: set[str] = set()
    for index, line in enumerate(lines):
        if starts_function_scope(line.content):
            declared.clear()

        if _inside_recent_map_context(lines, index):
            for match in BRACKET_LOOKUP_RE.finditer(line.content):
                lookup_name = match.group("name")
                if lookup_name not in declared:
                    return line

        declared.update(_declared_names(line.content))
    return None


def performance_reviewer(lines: list[DiffLine], language: str) -> list[Finding]:
    findings: list[Finding] = []

    for index, line in enumerate(lines):
        stripped = line.content.strip()
        if stripped.startswith(("for ", "for(")) and _loop_has_db_query(lines, index):
            append_unique(
                findings,
                finding(
                    line=line,
                    category=Category.performance,
                    severity="high",
                    title="N+1 query in loop",
                    description=(
                        "The loop performs a data lookup per item, which creates N database or "
                        "repository calls for N inputs."
                    ),
                    suggestion="Batch the lookup with an IN query or equivalent bulk API.",
                ),
            )

        if stripped.startswith(("for ", "for(")) and _loop_contains_await(lines, index):
            append_unique(
                findings,
                finding(
                    line=line,
                    category=Category.performance,
                    severity="high",
                    title="Await inside loop serializes independent work",
                    description=(
                        "Awaiting inside the loop makes independent operations run one after "
                        "another instead of concurrently."
                    ),
                    suggestion="Use Promise.all or a bounded concurrency helper for independent work.",
                ),
            )

    poll_line = _unbounded_polling_loop(lines)
    if poll_line:
        append_unique(
            findings,
            finding(
                line=poll_line,
                category=Category.performance,
                severity="critical",
                title="Unbounded polling loop",
                description="The polling loop has no timeout, max attempts, or cancellation path.",
                suggestion="Add a deadline, max retry count, or cancellation signal.",
            ),
        )

    undefined_lookup = _undefined_related_record_lookup(lines)
    if undefined_lookup:
        append_unique(
            findings,
            finding(
                line=undefined_lookup,
                category=Category.performance,
                severity="medium",
                title="Undefined related-record lookup in enrichment",
                description=(
                    "The enrichment references a related-record lookup that is not declared in "
                    "the local scope, which can throw and often points to missing batch-loading."
                ),
                suggestion="Load related records explicitly and key them by ID before enrichment.",
            ),
        )

    return findings
