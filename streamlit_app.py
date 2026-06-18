from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from infravox_reviewer.demo_ui import (
    DiffChoice,
    aggregate_reports,
    build_review_payload,
    category_counts,
    findings_table_html,
    load_diff_choices,
    severity_counts,
)


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def _badge(text: str, tone: str) -> str:
    colors = {
        "critical": ("#fecaca", "rgba(248, 113, 113, .14)", "rgba(248, 113, 113, .45)"),
        "high": ("#fed7aa", "rgba(251, 146, 60, .14)", "rgba(251, 146, 60, .45)"),
        "medium": ("#fde68a", "rgba(250, 204, 21, .13)", "rgba(250, 204, 21, .42)"),
        "low": ("#bfdbfe", "rgba(96, 165, 250, .13)", "rgba(96, 165, 250, .42)"),
        "clean": ("#bbf7d0", "rgba(74, 222, 128, .13)", "rgba(74, 222, 128, .42)"),
        "approve": ("#bbf7d0", "rgba(74, 222, 128, .13)", "rgba(74, 222, 128, .42)"),
        "needs_discussion": ("#fde68a", "rgba(250, 204, 21, .13)", "rgba(250, 204, 21, .42)"),
        "request_changes": ("#fecaca", "rgba(248, 113, 113, .14)", "rgba(248, 113, 113, .45)"),
    }
    foreground, background, border = colors.get(tone, ("#cbd5e1", "#111827", "#334155"))
    return (
        f"<span class='badge' style='color:{foreground};background:{background};"
        f"border-color:{border};'>{text}</span>"
    )


def _metric_card(label: str, value: str | int, tone: str = "neutral") -> str:
    return (
        f"<div class='metric-card metric-{tone}'>"
        f"<span>{label}</span>"
        f"<strong>{value}</strong>"
        "</div>"
    )


def _run_review(api_base_url: str, payload: dict[str, str | None]) -> dict[str, Any]:
    with httpx.Client(timeout=60) as client:
        response = client.post(f"{api_base_url.rstrip('/')}/review", json=payload)
        response.raise_for_status()
        return response.json()


def _run_all_reviews(
    api_base_url: str,
    choices: list[DiffChoice],
    context: str | None,
) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    progress = st.progress(0)
    status = st.empty()
    for index, choice in enumerate(choices, start=1):
        status.write(f"Reviewing {choice.filename}...")
        reports[choice.label] = _run_review(
            api_base_url,
            build_review_payload(choice=choice, context=context),
        )
        progress.progress(index / len(choices))
    status.empty()
    progress.empty()
    return reports


def _render_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #080c16;
            --panel: #111827;
            --panel-2: #172033;
            --line: rgba(148, 163, 184, .2);
            --text: #e5e7eb;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --accent-2: #fb7185;
        }
        .stApp {
            background:
                radial-gradient(circle at 18% 0%, rgba(56, 189, 248, .14), transparent 30%),
                radial-gradient(circle at 96% 4%, rgba(251, 113, 133, .11), transparent 28%),
                linear-gradient(180deg, #080c16 0%, #0a0f1c 100%);
            color: var(--text);
        }
        .block-container {
            padding-top: 1.7rem;
            padding-bottom: 3rem;
            max-width: 1320px;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
            border-right: 1px solid rgba(148, 163, 184, .16);
        }
        section[data-testid="stSidebar"] * {
            color: #e5e7eb;
        }
        div[data-testid="stTextInput"] input,
        div[data-baseweb="select"] > div {
            background: #080c16;
            border: 1px solid rgba(148, 163, 184, .24);
            color: #f8fafc;
            border-radius: 7px;
        }
        .stButton > button {
            background: linear-gradient(135deg, #fb7185 0%, #f43f5e 45%, #38bdf8 130%);
            border: 0;
            border-radius: 7px;
            color: white;
            font-weight: 800;
            letter-spacing: 0;
            min-height: 2.8rem;
            box-shadow: 0 16px 40px rgba(244, 63, 94, .22);
        }
        .hero {
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: 8px;
            padding: 1.35rem 1.45rem;
            background:
                linear-gradient(135deg, rgba(56, 189, 248, .16), rgba(251, 113, 133, .08)),
                #111827;
            box-shadow: 0 20px 60px rgba(0, 0, 0, .28);
        }
        .hero h1 {
            margin: 0 0 .35rem 0;
            font-size: 2rem;
            line-height: 1.2;
            letter-spacing: 0;
            color: #f8fafc;
        }
        .hero p {
            margin: 0;
            color: #b6c2d1;
            font-size: .98rem;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            border: 1px solid;
            border-radius: 999px;
            padding: .24rem .62rem;
            font-size: .78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0;
            white-space: nowrap;
        }
        .section-title {
            color: #f8fafc;
            font-size: 1rem;
            font-weight: 800;
            margin: .4rem 0 .6rem;
        }
        .summary-panel {
            border: 1px solid rgba(148, 163, 184, .16);
            border-radius: 8px;
            background: rgba(15, 23, 42, .72);
            padding: 1rem;
            margin-top: .65rem;
        }
        .metric-card {
            min-height: 86px;
            border: 1px solid rgba(148, 163, 184, .17);
            border-radius: 8px;
            padding: .82rem .9rem;
            background: linear-gradient(180deg, rgba(30, 41, 59, .95), rgba(15, 23, 42, .95));
            box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
        }
        .metric-card span {
            display: block;
            color: #94a3b8;
            font-size: .76rem;
            font-weight: 700;
            margin-bottom: .4rem;
        }
        .metric-card strong {
            color: #f8fafc;
            font-size: 1.6rem;
            line-height: 1.15;
            font-weight: 850;
            letter-spacing: 0;
        }
        .metric-critical { border-color: rgba(248, 113, 113, .35); }
        .metric-high { border-color: rgba(251, 146, 60, .35); }
        .metric-medium { border-color: rgba(250, 204, 21, .35); }
        .metric-security { border-color: rgba(248, 113, 113, .4); }
        .metric-performance { border-color: rgba(56, 189, 248, .36); }
        .metric-correctness { border-color: rgba(129, 140, 248, .4); }
        .metric-style { border-color: rgba(45, 212, 191, .36); }
        .metric-test_coverage { border-color: rgba(250, 204, 21, .38); }
        .mode-note {
            border: 1px solid rgba(56, 189, 248, .22);
            border-radius: 8px;
            padding: .72rem .85rem;
            background: rgba(56, 189, 248, .08);
            color: #bae6fd;
            margin-top: .75rem;
        }
        div[data-testid="stAlert"] {
            background: rgba(56, 189, 248, .12);
            border: 1px solid rgba(56, 189, 248, .28);
            color: #bae6fd;
            border-radius: 8px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: .45rem;
            border-bottom: 1px solid rgba(148, 163, 184, .18);
        }
        .stTabs [data-baseweb="tab"] {
            color: #cbd5e1;
            border-radius: 7px 7px 0 0;
            padding: .6rem .85rem;
        }
        .stTabs [aria-selected="true"] {
            color: #f8fafc;
            background: rgba(56, 189, 248, .12);
        }
        .table-shell {
            overflow-x: auto;
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: 8px;
            background: rgba(15, 23, 42, .8);
        }
        .findings-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1040px;
            color: #dbe4ee;
        }
        .findings-table th {
            position: sticky;
            top: 0;
            background: #111827;
            color: #93c5fd;
            font-size: .72rem;
            text-transform: uppercase;
            letter-spacing: 0;
            text-align: left;
            padding: .72rem .78rem;
            border-bottom: 1px solid rgba(148, 163, 184, .22);
        }
        .findings-table td {
            vertical-align: top;
            padding: .82rem .78rem;
            border-bottom: 1px solid rgba(148, 163, 184, .12);
            color: #dbe4ee;
            font-size: .86rem;
            line-height: 1.45;
        }
        .findings-table tr:nth-child(even) td {
            background: rgba(30, 41, 59, .35);
        }
        .findings-table tr:hover td {
            background: rgba(56, 189, 248, .08);
        }
        .id-cell {
            color: #93c5fd !important;
            font-weight: 800;
            white-space: nowrap;
        }
        .title-cell {
            color: #f8fafc !important;
            font-weight: 800;
            min-width: 220px;
        }
        .line-pill,
        .chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, .22);
            padding: .18rem .5rem;
            font-size: .72rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .line-pill {
            color: #bfdbfe;
            background: rgba(59, 130, 246, .12);
            border-color: rgba(59, 130, 246, .32);
        }
        .category-security { color: #fecaca; background: rgba(248,113,113,.13); border-color: rgba(248,113,113,.36); }
        .category-performance { color: #bae6fd; background: rgba(56,189,248,.12); border-color: rgba(56,189,248,.34); }
        .category-correctness { color: #c7d2fe; background: rgba(129,140,248,.13); border-color: rgba(129,140,248,.36); }
        .category-style { color: #99f6e4; background: rgba(45,212,191,.12); border-color: rgba(45,212,191,.34); }
        .category-test_coverage { color: #fde68a; background: rgba(250,204,21,.12); border-color: rgba(250,204,21,.34); }
        .severity-critical { color: #fecaca; background: rgba(248,113,113,.16); border-color: rgba(248,113,113,.42); }
        .severity-high { color: #fed7aa; background: rgba(251,146,60,.15); border-color: rgba(251,146,60,.4); }
        .severity-medium { color: #fde68a; background: rgba(250,204,21,.14); border-color: rgba(250,204,21,.36); }
        .severity-low { color: #bfdbfe; background: rgba(96,165,250,.13); border-color: rgba(96,165,250,.34); }
        .empty-state {
            border: 1px solid rgba(74, 222, 128, .28);
            background: rgba(74, 222, 128, .1);
            color: #bbf7d0;
            border-radius: 8px;
            padding: 1rem;
        }
        pre, code {
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="InfraVox Review Demo",
        page_icon="IV",
        layout="wide",
    )
    _render_css()

    choices = load_diff_choices()
    if not choices:
        st.error("No diff files found in the local diffs/ folder.")
        return

    with st.sidebar:
        st.header("Review Input")
        api_base_url = st.text_input("FastAPI base URL", value=DEFAULT_API_BASE_URL)
        review_mode = st.radio(
            "Mode",
            ["Single diff", "All local diffs"],
            horizontal=False,
        )
        if review_mode == "Single diff":
            selected_label = st.selectbox("Diff", [choice.label for choice in choices])
            selected_choice = next(choice for choice in choices if choice.label == selected_label)
            context_value = f"Review {selected_choice.filename} for assignment demo"
        else:
            selected_choice = choices[0]
            context_value = f"Review all {len(choices)} diffs for demo"
            st.markdown(
                f"<div class='mode-note'>{len(choices)} diffs will be reviewed.</div>",
                unsafe_allow_html=True,
            )
        context = st.text_input(
            "Context",
            value=context_value,
            key=f"context_{review_mode}",
        )
        run_clicked = st.button("Run Review", type="primary", width="stretch")

        st.divider()
        st.caption("Start the API first:")
        st.code("uvicorn infravox_reviewer.main:app --reload", language="bash")

    st.markdown(
        """
        <div class="hero">
          <h1>InfraVox AI Code Reviewer</h1>
          <p>Live demo view for the FastAPI + LangGraph review pipeline, rendered as a structured PR review.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(
        "Selected diff preview" if review_mode == "Single diff" else "Local diff previews",
        expanded=False,
    ):
        preview_choices = [selected_choice] if review_mode == "Single diff" else choices
        for preview_choice in preview_choices:
            st.caption(preview_choice.label)
            st.code(
                preview_choice.path.read_text(encoding="utf-8"),
                language=preview_choice.language,
            )

    if "report" not in st.session_state and "all_reports" not in st.session_state:
        st.info("Choose a diff and run the review to populate the report.")

    if run_clicked:
        with st.spinner("Posting diff to FastAPI /review..."):
            try:
                if review_mode == "All local diffs":
                    st.session_state.all_reports = _run_all_reviews(api_base_url, choices, context)
                    st.session_state.report = None
                    st.session_state.last_mode = review_mode
                else:
                    payload = build_review_payload(choice=selected_choice, context=context)
                    st.session_state.report = _run_review(api_base_url, payload)
                    st.session_state.all_reports = None
                    st.session_state.last_choice = selected_choice.label
                    st.session_state.last_mode = review_mode
            except httpx.HTTPError as exc:
                st.error(f"Could not reach the review API: {exc}")
                return

    all_reports = st.session_state.get("all_reports")
    report = st.session_state.get("report")
    if all_reports:
        aggregate = aggregate_reports(all_reports)
        st.divider()
        st.markdown('<div class="section-title">Diff Run Summary</div>', unsafe_allow_html=True)
        st.markdown(
            f"<div class='summary-panel'><strong>Reviewed {aggregate['diff_count']} diffs.</strong><br>"
            "<span style='color:#94a3b8'>Aggregated status across every selected local diff.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        summary_cols = st.columns([1, 1, 1, 1])
        aggregate_cards = [
            ("Diffs", aggregate["diff_count"], "neutral"),
            ("Findings", aggregate["total_findings"], "neutral"),
            ("Severity", aggregate["overall_severity"], aggregate["overall_severity"]),
            ("Processing", f"{aggregate['processing_time_ms']} ms", "neutral"),
        ]
        for column, (label, value, tone) in zip(summary_cols, aggregate_cards, strict=True):
            column.markdown(_metric_card(label, value, tone), unsafe_allow_html=True)

        st.markdown(
            " ".join(
                [
                    _badge(str(aggregate["verdict"]).replace("_", " "), str(aggregate["verdict"])),
                    _badge(str(aggregate["overall_severity"]), str(aggregate["overall_severity"])),
                ]
            ),
            unsafe_allow_html=True,
        )

        diff_tabs = st.tabs(["All Diff Overview", "Inspect One Diff"])
        with diff_tabs[0]:
            st.markdown('<div class="section-title">Per-Diff Results</div>', unsafe_allow_html=True)
            overview_cols = st.columns(len(all_reports))
            for column, (label, item) in zip(overview_cols, all_reports.items(), strict=True):
                column.markdown(
                    "<div class='summary-panel'>"
                    f"<strong>{label}</strong><br>"
                    f"<span style='color:#94a3b8'>{item['verdict']} | "
                    f"{item['overall_severity']} | {len(item.get('findings', []))} findings</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

            category_cols = st.columns(5)
            for index, category in enumerate(
                ["security", "performance", "correctness", "style", "test_coverage"]
            ):
                category_cols[index].markdown(
                    _metric_card(
                        category.replace("_", " ").title(),
                        aggregate["category_counts"].get(category, 0),
                        category,
                    ),
                    unsafe_allow_html=True,
                )

            severity_cols = st.columns(4)
            for index, severity in enumerate(["critical", "high", "medium", "low"]):
                severity_cols[index].markdown(
                    _metric_card(
                        severity.title(),
                        aggregate["severity_counts"].get(severity, 0),
                        severity,
                    ),
                    unsafe_allow_html=True,
                )

        with diff_tabs[1]:
            detail_label = st.selectbox("Detailed report", list(all_reports), key="detail_report")
            _render_report(all_reports[detail_label])
        return

    if not report:
        return

    _render_report(report)


def _render_report(report: dict[str, Any]) -> None:
    st.divider()
    st.markdown('<div class="section-title">Review Summary</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='summary-panel'><strong>{report['pr_summary']}</strong><br>"
        f"<span style='color:#94a3b8'>{report['verdict_reason']}</span></div>",
        unsafe_allow_html=True,
    )

    summary_cols = st.columns([1.25, 1, 1, 1])
    summary_cards = [
        ("Verdict", report["verdict"].replace("_", " "), report["verdict"]),
        ("Severity", report["overall_severity"], report["overall_severity"]),
        ("Findings", len(report.get("findings", [])), "neutral"),
        ("Processing", f'{report.get("processing_time_ms", 0)} ms', "neutral"),
    ]
    for column, (label, value, tone) in zip(summary_cols, summary_cards, strict=True):
        column.markdown(_metric_card(label, value, tone), unsafe_allow_html=True)

    st.markdown(
        " ".join(
            [
                _badge(report["verdict"].replace("_", " "), report["verdict"]),
                _badge(report["overall_severity"], report["overall_severity"]),
            ]
        ),
        unsafe_allow_html=True,
    )
    tabs = st.tabs(["Findings Table", "Agent Counts", "Missing Tests", "Raw JSON"])

    with tabs[0]:
        st.markdown(findings_table_html(report), unsafe_allow_html=True)

    with tabs[1]:
        category_cols = st.columns(5)
        counts = category_counts(report)
        for index, category in enumerate(
            ["security", "performance", "correctness", "style", "test_coverage"]
        ):
            category_cols[index].markdown(
                _metric_card(category.replace("_", " ").title(), counts.get(category, 0), category),
                unsafe_allow_html=True,
            )

        severity_cols = st.columns(4)
        severities = severity_counts(report)
        for index, severity in enumerate(["critical", "high", "medium", "low"]):
            severity_cols[index].markdown(
                _metric_card(severity.title(), severities.get(severity, 0), severity),
                unsafe_allow_html=True,
            )

    with tabs[2]:
        missing_tests = report.get("missing_tests", [])
        if missing_tests:
            for item in missing_tests:
                st.markdown(f"- {item}")
        else:
            st.success("No missing test suggestions were returned.")

    with tabs[3]:
        st.json(report)


if __name__ == "__main__":
    main()
