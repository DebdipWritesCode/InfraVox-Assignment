from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from scripts.run_reviews import infer_language


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIFFS_DIR = PROJECT_ROOT / "diffs"
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "clean": 4}
VERDICT_ORDER = {"request_changes": 0, "needs_discussion": 1, "approve": 2}


@dataclass(frozen=True)
class DiffChoice:
    label: str
    filename: str
    path: Path
    language: str


def _format_label(filename: str, language: str) -> str:
    prefix = filename.split("_", 1)[0].replace("diff", "Diff ")
    return f"{prefix} - {language.title()}"


def load_diff_choices(diffs_dir: Path = DEFAULT_DIFFS_DIR) -> list[DiffChoice]:
    diff_paths = sorted(
        path
        for pattern in ("diff*.txt", "*.diff", "*.patch")
        for path in diffs_dir.glob(pattern)
        if path.is_file()
    )
    return [
        DiffChoice(
            label=_format_label(path.name, infer_language(path.name)),
            filename=path.name,
            path=path,
            language=infer_language(path.name),
        )
        for path in diff_paths
    ]


def build_review_payload(choice: DiffChoice, context: str | None = None) -> dict[str, str | None]:
    normalized_context = context.strip() if context else None
    return {
        "diff": choice.path.read_text(encoding="utf-8"),
        "language": choice.language,
        "context": normalized_context or None,
    }


def findings_table_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for finding in report.get("findings", []):
        rows.append(
            {
                "ID": finding.get("id", ""),
                "Line": finding.get("line", ""),
                "Category": finding.get("category", ""),
                "Severity": finding.get("severity", ""),
                "Title": finding.get("title", ""),
                "Description": finding.get("description", ""),
                "Suggestion": finding.get("suggestion", ""),
            }
        )
    return rows


def findings_table_html(report: dict[str, Any]) -> str:
    rows = findings_table_rows(report)
    if not rows:
        return "<div class='empty-state'>No findings returned for this diff.</div>"

    body = []
    for row in rows:
        category = escape(str(row["Category"]))
        severity = escape(str(row["Severity"]))
        body.append(
            "<tr>"
            f"<td class='id-cell'>{escape(str(row['ID']))}</td>"
            f"<td><span class='line-pill'>{escape(str(row['Line']))}</span></td>"
            f"<td><span class='chip category-{category}'>{category}</span></td>"
            f"<td><span class='chip severity-{severity}'>{severity}</span></td>"
            f"<td class='title-cell'>{escape(str(row['Title']))}</td>"
            f"<td>{escape(str(row['Description']))}</td>"
            f"<td>{escape(str(row['Suggestion']))}</td>"
            "</tr>"
        )

    return (
        "<div class='table-shell'>"
        "<table class='findings-table'>"
        "<thead><tr>"
        "<th>ID</th><th>Line</th><th>Category</th><th>Severity</th>"
        "<th>Title</th><th>Description</th><th>Suggestion</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table>"
        "</div>"
    )


def category_counts(report: dict[str, Any]) -> dict[str, int]:
    counts = Counter(finding.get("category", "") for finding in report.get("findings", []))
    counts.pop("", None)
    return dict(sorted(counts.items()))


def severity_counts(report: dict[str, Any]) -> dict[str, int]:
    counts = Counter(finding.get("severity", "") for finding in report.get("findings", []))
    counts.pop("", None)
    return dict(sorted(counts.items()))


def aggregate_reports(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings = [
        finding
        for report in reports.values()
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
    ]
    category_counter = Counter(finding.get("category", "") for finding in findings)
    severity_counter = Counter(finding.get("severity", "") for finding in findings)
    category_counter.pop("", None)
    severity_counter.pop("", None)

    severities = [str(report.get("overall_severity", "clean")) for report in reports.values()]
    verdicts = [str(report.get("verdict", "approve")) for report in reports.values()]
    overall_severity = min(severities, key=lambda item: SEVERITY_ORDER.get(item, 99), default="clean")
    verdict = min(verdicts, key=lambda item: VERDICT_ORDER.get(item, 99), default="approve")

    return {
        "diff_count": len(reports),
        "total_findings": len(findings),
        "processing_time_ms": sum(
            int(report.get("processing_time_ms", 0)) for report in reports.values()
        ),
        "overall_severity": overall_severity,
        "verdict": verdict,
        "category_counts": dict(sorted(category_counter.items())),
        "severity_counts": dict(sorted(severity_counter.items())),
    }
