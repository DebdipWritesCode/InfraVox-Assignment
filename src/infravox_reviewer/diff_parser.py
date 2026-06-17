from __future__ import annotations

import re

from .models import DiffLine


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _normalize_new_file_path(raw_line: str) -> str | None:
    path = raw_line[4:].strip()
    if path == "/dev/null":
        return None
    if path.startswith("b/"):
        return path[2:]
    return path or None


def extract_added_lines(diff: str) -> list[DiffLine]:
    """Return added code lines with unified-diff line numbers when available."""
    added: list[DiffLine] = []
    current_file: str | None = None
    new_line_number: int | None = None

    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ "):
            current_file = _normalize_new_file_path(raw_line)
            continue

        hunk_match = HUNK_RE.match(raw_line)
        if hunk_match:
            new_line_number = int(hunk_match.group(1))
            continue

        if not raw_line.startswith("+"):
            if new_line_number is not None and raw_line and not raw_line.startswith("-"):
                new_line_number += 1
            continue

        content = raw_line[1:].rstrip()
        line_number = new_line_number if new_line_number is not None else len(added) + 1
        added.append(
            DiffLine(
                number=line_number,
                content=content.lstrip(),
                file_path=current_file,
            )
        )
        if new_line_number is not None:
            new_line_number += 1

    return added
