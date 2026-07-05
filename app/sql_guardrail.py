"""Validate that an LLM-generated query is a single, read-only SELECT.

Kept dependency-free and pure so it can be unit-tested without a database or
network. The LLM module imports `is_safe_select` from here.
"""
from __future__ import annotations

import re

# Statement keywords that must never appear in a read-only query.
_FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "attach", "detach", "copy", "pragma", "install", "load", "export",
    "import", "call", "set", "vacuum", "merge", "replace", "grant", "revoke",
}

_WORD_RE = re.compile(r"[a-zA-Z_]+")
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    return _COMMENT_RE.sub(" ", sql)


def is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (is_safe, reason). A query is safe only if it is a single
    statement that begins with SELECT or WITH and contains no mutating verbs."""
    if not sql or not sql.strip():
        return False, "Empty query."

    cleaned = _strip_comments(sql).strip()

    # Disallow statement chaining. A single trailing semicolon is fine.
    body = cleaned[:-1] if cleaned.endswith(";") else cleaned
    if ";" in body:
        return False, "Multiple statements are not allowed."

    lowered = body.lower().lstrip()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Query must start with SELECT or WITH."

    words = {w.lower() for w in _WORD_RE.findall(body)}
    hit = words & _FORBIDDEN
    if hit:
        return False, f"Forbidden keyword(s): {', '.join(sorted(hit))}."

    return True, "ok"
