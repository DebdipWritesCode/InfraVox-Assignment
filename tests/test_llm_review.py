from infravox_reviewer.llm_review import build_llm_review_prompt, parse_llm_findings


def test_parse_llm_findings_accepts_fenced_json_response():
    content = """```json
{
  "findings": [
    {
      "line": 7,
      "line_content": "db.query(sql)",
      "category": "security",
      "severity": "high",
      "title": "Possible SQL injection",
      "description": "The query uses request data without parameterization.",
      "suggestion": "Use a parameterized query."
    }
  ]
}
```"""

    findings = parse_llm_findings(content)

    assert len(findings) == 1
    assert findings[0].line == 7
    assert findings[0].category == "security"
    assert findings[0].severity == "high"
    assert findings[0].title == "Possible SQL injection"


def test_parse_llm_findings_returns_empty_list_for_non_json_response():
    assert parse_llm_findings("I would approve this change.") == []


def test_build_llm_review_prompt_redacts_secret_patterns():
    prompt = build_llm_review_prompt(
        diff="+STRIPE_SECRET_KEY = 'sk_live_1234567890abcdef'",
        language="python",
        context=None,
        baseline_findings=[],
    )

    assert "sk_live_" not in prompt
    assert "[REDACTED_SECRET]" in prompt
