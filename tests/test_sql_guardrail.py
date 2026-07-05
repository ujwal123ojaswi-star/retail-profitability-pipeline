"""Unit tests for the read-only SQL guardrail."""
from app.sql_guardrail import is_safe_select


def test_allows_plain_select():
    ok, _ = is_safe_select("SELECT company_id, gross_margin FROM fct_profitability")
    assert ok


def test_allows_with_cte():
    ok, _ = is_safe_select(
        "WITH g AS (SELECT * FROM fct_profitability) SELECT max(gross_margin) FROM g"
    )
    assert ok


def test_allows_trailing_semicolon():
    ok, _ = is_safe_select("SELECT 1 FROM fct_profitability;")
    assert ok


def test_rejects_empty():
    ok, _ = is_safe_select("   ")
    assert not ok


def test_rejects_non_select_start():
    ok, reason = is_safe_select("EXPLAIN SELECT * FROM fct_profitability")
    assert not ok


def test_rejects_delete():
    # Rejected because it doesn't start with SELECT/WITH (the start-check fires first).
    ok, _ = is_safe_select("DELETE FROM fct_profitability")
    assert not ok


def test_rejects_update_inside_select_context():
    # A mutating verb appearing after a valid SELECT start is caught by the keyword check.
    ok, reason = is_safe_select("SELECT * FROM (UPDATE fct_profitability SET x=1)")
    assert not ok
    assert "update" in reason.lower()


def test_rejects_drop():
    ok, _ = is_safe_select("SELECT 1; DROP TABLE fct_profitability")
    assert not ok


def test_rejects_statement_chaining():
    ok, reason = is_safe_select(
        "SELECT * FROM fct_profitability; SELECT * FROM dim_company"
    )
    assert not ok
    assert "multiple" in reason.lower()


def test_rejects_attach_exfiltration():
    ok, _ = is_safe_select("ATTACH 'evil.db' AS e; SELECT * FROM e.secrets")
    assert not ok


def test_ignores_keyword_in_comment():
    # A forbidden word inside a comment should be stripped before the check.
    ok, _ = is_safe_select("SELECT revenue FROM fct_profitability -- no drop here")
    assert ok
