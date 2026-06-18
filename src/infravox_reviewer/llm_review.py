from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .llm import build_chat_groq
from .models import DiffLine, Finding


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)\s*```", re.DOTALL | re.IGNORECASE)
SECRET_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9_]+"),
    re.compile(r"gsk_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"xoxb-[A-Za-z0-9-]+"),
)


def _message_content(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    return str(content)


def _extract_json_payload(content: str) -> Any:
    fenced_match = JSON_BLOCK_RE.search(content)
    candidate = fenced_match.group("body") if fenced_match else content.strip()
    if not candidate:
        raise ValueError("empty LLM response")

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(candidate[start : end + 1])


def redact_secrets(content: str) -> str:
    redacted = content
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def parse_llm_findings(content: str) -> list[Finding]:
    try:
        payload = _extract_json_payload(content)
    except (json.JSONDecodeError, ValueError):
        return []

    raw_findings = payload.get("findings", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_findings, list):
        return []

    findings: list[Finding] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            continue
        try:
            findings.append(
                Finding.model_validate(
                    {
                        **raw_finding,
                        "id": "",
                    }
                )
            )
        except ValidationError:
            continue
    return findings


def _findings_json(findings: list[Finding]) -> str:
    findings_json = json.dumps(
        [
            {
                "line": finding.line,
                "line_content": finding.line_content,
                "category": finding.category.value,
                "severity": finding.severity,
                "title": finding.title,
                "description": finding.description,
                "suggestion": finding.suggestion,
            }
            for finding in findings
        ],
        indent=2,
        ensure_ascii=False,
    )
    return redact_secrets(findings_json)


def build_specialist_review_prompt(
    *,
    agent_name: str,
    category: str,
    responsibility: str,
    diff: str,
    language: str,
    context: str | None,
    fallback_findings: list[Finding],
) -> str:
    context_line = context or "No extra PR context was provided."
    return f"""You are {agent_name}, an AI specialist reviewer inside a LangGraph multi-agent code review pipeline.

Your responsibility:
{responsibility}

Review only the {category} dimension. Return findings only for category "{category}".
The deterministic pre-checks below are seed findings for this same specialist dimension.
Validate them, keep the high-confidence ones, and add any additional high-confidence,
line-level findings that are visible in the diff.

Return only valid JSON in this exact shape:
{{
  "findings": [
    {{
      "line": 42,
      "line_content": "exact line of code from the diff",
      "category": "security|performance|correctness|style|test_coverage",
      "severity": "critical|high|medium|low",
      "title": "short issue title",
      "description": "plain-English explanation of why this matters",
      "suggestion": "concrete fix"
    }}
  ]
}}

If there are no high-confidence {category} findings, return {{"findings": []}}.

Language: {language}
Context: {context_line}

Seed findings for this specialist:
{_findings_json(fallback_findings)}

Raw diff:
{redact_secrets(diff)}
"""


def build_llm_review_prompt(
    *,
    diff: str,
    language: str,
    context: str | None,
    baseline_findings: list[Finding],
) -> str:
    return build_specialist_review_prompt(
        agent_name="llm_reviewer",
        category="correctness",
        responsibility="Review the diff for additional high-confidence issues.",
        diff=diff,
        language=language,
        context=context,
        fallback_findings=baseline_findings,
    )


def ai_specialist_reviewer(
    *,
    agent_name: str,
    category: str,
    responsibility: str,
    diff: str,
    language: str,
    context: str | None,
    lines: list[DiffLine],
    fallback_findings: list[Finding],
) -> list[Finding]:
    llm = build_chat_groq()
    if llm is None:
        return fallback_findings

    prompt = build_specialist_review_prompt(
        agent_name=agent_name,
        category=category,
        responsibility=responsibility,
        diff=diff,
        language=language,
        context=context,
        fallback_findings=fallback_findings,
    )
    try:
        response = llm.invoke(prompt)
    except Exception:
        return fallback_findings

    line_numbers = {line.number for line in lines}
    findings = [
        finding
        for finding in parse_llm_findings(_message_content(response))
        if finding.line in line_numbers and finding.category.value == category
    ]
    if not findings and fallback_findings:
        return fallback_findings
    return findings
