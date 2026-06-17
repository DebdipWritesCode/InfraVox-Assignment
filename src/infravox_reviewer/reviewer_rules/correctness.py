from __future__ import annotations

import re

from ..models import Category, DiffLine, Finding
from .common import append_unique, find_line, finding


LOOKUP_ASSIGNMENT_RE = re.compile(
    r"^\s*(?:const|let|var)?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:await\s+)?.*"
    r"(find|get|fetch|query|first|one)\w*\s*\("
)


def _lookup_without_guard(lines: list[DiffLine]) -> DiffLine | None:
    for index, line in enumerate(lines):
        match = LOOKUP_ASSIGNMENT_RE.search(line.content)
        if not match:
            continue
        name = match.group("name")
        following = lines[index + 1 : index + 5]
        guard_pattern = rf"(if\s+not\s+{name}|if\s+{name}\s+is\s+None|if\s*\(!{name}\))"
        has_guard = any(re.search(guard_pattern, item.content) for item in following)
        dereference = next(
            (
                item
                for item in following
                if re.search(rf"\b{name}(\.|\[)", item.content)
                and not (".push(" in item.content and f"{name}[0]" in item.content)
                and not ("db.query" in line.content.lower() and f"{name}.map(" in item.content)
                and not item.content.strip().startswith("if ")
            ),
            None,
        )
        if dereference and not has_guard:
            return dereference
    return None


def _unvalidated_request_json(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: "request.json" in line.content.lower()
        and "=" in line.content
        and not any(
            token in line.content.lower() for token in ("schema", "validate", "model_validate")
        ),
    )


def _missing_query_param_validation(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: ".split(" in line.content
        and not any(marker in line.content for marker in ("if ", "typeof", "validate")),
    )


def _missing_result_handling(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(lines, lambda line: re.search(r"\.push\([^)]*\[0\]\)", line.content) is not None)


def _file_open_without_context(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: "open(" in line.content and ".read()" in line.content and "with " not in line.content,
    )


def _unknown_map_lookup(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: re.search(r"\[[A-Za-z_][A-Za-z0-9_]*\]", line.content) is not None
        and any(marker in line.content.lower() for marker in ("discount", "map", "lookup")),
    )


def correctness_reviewer(lines: list[DiffLine], language: str) -> list[Finding]:
    findings: list[Finding] = []

    null_deref = _lookup_without_guard(lines)
    if null_deref:
        append_unique(
            findings,
            finding(
                line=null_deref,
                category=Category.correctness,
                severity="high",
                title="Possible null dereference after lookup",
                description="A lookup result is dereferenced without a visible not-found guard.",
                suggestion="Check for a missing result before reading fields from the object.",
            ),
        )

    json_line = _unvalidated_request_json(lines)
    if json_line:
        append_unique(
            findings,
            finding(
                line=json_line,
                category=Category.correctness,
                severity="high",
                title="Request JSON is used without validation",
                description="The request body is read without visible schema or field validation.",
                suggestion="Validate required fields and types before using request data.",
            ),
        )

    split_line = _missing_query_param_validation(lines)
    if split_line:
        append_unique(
            findings,
            finding(
                line=split_line,
                category=Category.correctness,
                severity="high",
                title="Missing query parameter validation",
                description="The code calls a string method on query input without a type check.",
                suggestion="Validate the query parameter exists and is a string before parsing it.",
            ),
        )

    result_line = _missing_result_handling(lines)
    if result_line:
        append_unique(
            findings,
            finding(
                line=result_line,
                category=Category.correctness,
                severity="medium",
                title="Missing result handling",
                description="The code uses the first result without checking whether a row exists.",
                suggestion="Handle missing rows explicitly before adding them to the response.",
            ),
        )

    file_line = _file_open_without_context(lines)
    if file_line:
        append_unique(
            findings,
            finding(
                line=file_line,
                category=Category.correctness,
                severity="medium",
                title="File opened without context manager",
                description="The file handle is opened and read without a context manager.",
                suggestion="Use a `with open(...) as file:` block so the handle is closed.",
            ),
        )

    map_line = _unknown_map_lookup(lines)
    if map_line:
        append_unique(
            findings,
            finding(
                line=map_line,
                category=Category.correctness,
                severity="high",
                title="Unknown map key can produce invalid result",
                description="A dynamic key is read from a map without validating that the key exists.",
                suggestion="Validate the key or provide an explicit fallback before calculating.",
            ),
        )

    return findings
