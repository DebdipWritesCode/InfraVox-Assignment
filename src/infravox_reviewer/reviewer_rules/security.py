from __future__ import annotations

import re

from ..models import Category, DiffLine, Finding
from .common import append_unique, find_line, finding, starts_function_scope


def _looks_like_sql(content: str) -> bool:
    lowered = content.lower()
    return any(keyword in lowered for keyword in ("select ", "update ", "insert ", "delete "))


def _uses_dynamic_sql(content: str) -> bool:
    if not _looks_like_sql(content):
        return False
    lowered = content.lower()
    return (
        " + " in content
        or "+ str(" in content
        or (content.lstrip().startswith(("query = f", "sql = f")) and "{" in content)
        or ("`" in content and any(token in lowered for token in ("req.", "request.", "${")))
        or ("{" in content and "}" in content and ("f\"" in content or "f'" in content))
    )


def _looks_like_secret_assignment(content: str) -> bool:
    lowered = content.lower()
    name_mentions_secret = any(
        marker in lowered for marker in ("secret", "api_key", "apikey", "token", "private_key")
    )
    assigned_string = bool(re.search(r"=\s*['\"][^'\"]{12,}['\"]", content))
    known_token_prefix = any(marker in content for marker in ("sk_live", "ghp_", "gsk_", "xoxb-"))
    return "=" in content and name_mentions_secret and (assigned_string or known_token_prefix)


def _is_password_update_without_hash(content: str) -> bool:
    lowered = content.lower()
    return (
        "update " in lowered
        and "password" in lowered
        and "hash" not in lowered
        and "bcrypt" not in lowered
        and "argon2" not in lowered
    )


def _auth_sensitive_function(lines: list[DiffLine]) -> DiffLine | None:
    sensitive_terms = ("reset", "password", "cancel", "refund", "delete", "admin", "approve")
    auth_terms = ("auth", "permission", "owner", "user.id", "req.user", "current_user", "token")
    for index, line in enumerate(lines):
        if not starts_function_scope(line.content):
            continue
        lowered = line.content.lower()
        if not any(term in lowered for term in sensitive_terms):
            continue
        window = " ".join(item.content.lower() for item in lines[index : index + 8])
        mutates_sensitive_state = any(
            term in window for term in ("update ", "save(", "status =", "refund", "password")
        )
        has_auth_check = any(term in window for term in auth_terms)
        if mutates_sensitive_state and not has_auth_check:
            return line
    return None


def _unescaped_template_interpolation(lines: list[DiffLine]) -> DiffLine | None:
    return find_line(
        lines,
        lambda line: "replace(" in line.content
        and "{{" in line.content
        and "escape" not in line.content.lower(),
    )


def security_reviewer(lines: list[DiffLine], language: str) -> list[Finding]:
    findings: list[Finding] = []

    for line in lines:
        if _uses_dynamic_sql(line.content):
            append_unique(
                findings,
                finding(
                    line=line,
                    category=Category.security,
                    severity="critical",
                    title="Dynamic SQL construction can allow injection",
                    description=(
                        "The SQL statement is assembled from runtime values. If any value is "
                        "user-controlled, an attacker can alter the query."
                    ),
                    suggestion=(
                        "Use parameterized queries or a query builder instead of string "
                        "concatenation, f-strings, or template interpolation."
                    ),
                ),
            )

        if _looks_like_secret_assignment(line.content):
            append_unique(
                findings,
                finding(
                    line=line,
                    category=Category.security,
                    severity="critical",
                    title="Hardcoded secret value",
                    description=(
                        "A credential-like value is assigned in source code, which can expose it "
                        "to anyone with repository access."
                    ),
                    suggestion=(
                        "Move secrets to environment variables or a secret manager, rotate the "
                        "exposed value, and enable secret scanning."
                    ),
                ),
            )

        if _is_password_update_without_hash(line.content):
            append_unique(
                findings,
                finding(
                    line=line,
                    category=Category.security,
                    severity="critical",
                    title="Password update stores un-hashed password input",
                    description=(
                        "The password update writes password input without evidence of hashing."
                    ),
                    suggestion="Hash passwords with bcrypt or argon2 before storing them.",
                ),
            )

    auth_line = _auth_sensitive_function(lines)
    if auth_line:
        append_unique(
            findings,
            finding(
                line=auth_line,
                category=Category.security,
                severity="high",
                title="Authorization check missing for sensitive operation",
                description=(
                    "The code performs a sensitive mutation without a visible ownership, role, "
                    "or token validation check."
                ),
                suggestion=(
                    "Check that the authenticated caller is allowed to perform this operation "
                    "before changing state."
                ),
            ),
        )

    template_line = _unescaped_template_interpolation(lines)
    if template_line:
        append_unique(
            findings,
            finding(
                line=template_line,
                category=Category.security,
                severity="high",
                title="Unescaped HTML/template interpolation",
                description="The code injects content into a template without visible escaping.",
                suggestion="Use an escaping-aware template renderer or HTML-escape the value.",
            ),
        )

    return findings
