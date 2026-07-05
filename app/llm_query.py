"""Optional natural-language query layer.

A stakeholder types a question; the model writes a single read-only DuckDB
SELECT against the fct_profitability schema; the guardrail validates it; we run
it read-only and (optionally) ask the model to phrase a one-line answer.

This module is import-safe even if `anthropic` is not installed -- the import is
deferred into the call so the dashboard can offer the feature conditionally.
"""
from __future__ import annotations

import os

import duckdb
import pandas as pd

from app.sql_guardrail import is_safe_select

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 400

_SQL_SYSTEM_PROMPT = """\
You write a single read-only DuckDB SQL SELECT against the table below.
Return ONLY the SQL, with no prose, no explanation, and no markdown fences.
Use only this table and these columns. Do not invent columns.

Table: fct_profitability
Columns:
  profitability_id text, company_id text, company_name text, ticker text,
  strategy text, quarter_start date, year int, quarter int,
  revenue double, cost_of_revenue double, gross_profit double,
  operating_income double, net_income double, assets double, liabilities double,
  gross_margin double, operating_margin double, net_margin double,
  revenue_yoy double, cpi double, retail_sales double, consumer_sentiment double,
  unemployment double, fed_funds double

Rules:
- company_id is 'WMT' (Walmart, cost leadership) or 'TGT' (Target, differentiation).
- margins are fractions (0.25 = 25%).
- Always write a single SELECT (a leading WITH is allowed). Never modify data.
"""


def _get_client():
    # Deferred import so the rest of the app loads without the SDK installed.
    from anthropic import Anthropic

    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _extract_text(message) -> str:
    return "".join(block.text for block in message.content if block.type == "text").strip()


def generate_sql(question: str) -> str:
    """Ask the model for a SELECT answering the question."""
    client = _get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SQL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    sql = _extract_text(message)
    # Strip an accidental code fence if the model adds one anyway.
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.split("\n", 1)[-1] if sql.lower().startswith("sql") else sql
    return sql.strip()


def run_readonly(sql: str, warehouse_path: str) -> pd.DataFrame:
    """Run a validated SELECT against the warehouse in read-only mode."""
    con = duckdb.connect(warehouse_path, read_only=True)
    try:
        return con.execute(sql).fetch_df()
    finally:
        con.close()


def phrase_answer(question: str, result: pd.DataFrame) -> str:
    """Ask the model to summarize the result table in one sentence."""
    client = _get_client()
    preview = result.head(20).to_markdown(index=False)
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system="Answer the user's question in one concise sentence using only the table provided.",
        messages=[{"role": "user", "content": f"Question: {question}\n\nResult:\n{preview}"}],
    )
    return _extract_text(message)


def ask(question: str, warehouse_path: str) -> dict:
    """End-to-end: question -> SQL -> guardrail -> result -> phrased answer.

    Returns a dict with keys: sql, ok, reason, result (DataFrame or None), answer.
    """
    sql = generate_sql(question)
    ok, reason = is_safe_select(sql)
    if not ok:
        return {"sql": sql, "ok": False, "reason": reason, "result": None, "answer": None}

    result = run_readonly(sql, warehouse_path)
    answer = phrase_answer(question, result) if not result.empty else "No rows matched."
    return {"sql": sql, "ok": True, "reason": reason, "result": result, "answer": answer}
