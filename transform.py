"""Run the dbt SQL models directly against DuckDB -- no dbt required.

dbt does not yet support Python 3.14, so this module executes the exact same
.sql files in dependency order by doing the small substitutions dbt would do
(`ref`, `source`, `config`) and materializing each model as a view or table.
It then runs the same data-quality checks the dbt schema tests would.

The .sql files remain the canonical models; this is just a lightweight runner
so the project builds on 3.14. On Python <=3.13 you can use real dbt instead
(`pip install -e ".[dbt]"` then `dbt build`).
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

from ingest.config import WAREHOUSE_PATH

DBT_MODELS_DIR = Path(__file__).resolve().parent / "dbt" / "models"

# (model_name, folder, materialization) in dependency order.
MODELS = [
    ("stg_sec_financials", "staging", "view"),
    ("stg_fred_macro", "staging", "view"),
    ("int_quarterly_metrics", "intermediate", "view"),
    ("dim_company", "marts", "table"),
    ("fct_profitability", "marts", "table"),
]

# Data-quality checks: each query must return 0. Mirrors the dbt schema tests.
CHECKS = [
    ("dim_company.company_id not_null",
     "select count(*) from main.dim_company where company_id is null"),
    ("dim_company.company_id unique",
     "select count(*) - count(distinct company_id) from main.dim_company"),
    ("dim_company.strategy accepted_values",
     "select count(*) from main.dim_company "
     "where strategy not in ('cost leadership', 'differentiation')"),
    ("fct_profitability.profitability_id not_null",
     "select count(*) from main.fct_profitability where profitability_id is null"),
    ("fct_profitability.profitability_id unique",
     "select count(*) - count(distinct profitability_id) from main.fct_profitability"),
    ("fct_profitability.company_id relationships",
     "select count(*) from main.fct_profitability f "
     "left join main.dim_company d on f.company_id = d.company_id "
     "where d.company_id is null"),
    ("fct_profitability.gross_margin accepted_range",
     "select count(*) from main.fct_profitability "
     "where gross_margin is not null and (gross_margin < -1 or gross_margin > 1)"),
    ("fct_profitability.operating_margin accepted_range",
     "select count(*) from main.fct_profitability "
     "where operating_margin is not null and (operating_margin < -1 or operating_margin > 1)"),
]

_REF_RE = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_SOURCE_RE = re.compile(
    r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)
_CONFIG_RE = re.compile(r"\{\{\s*config\([^}]*\)\s*\}\}")


def render_sql(raw_sql: str) -> str:
    """Resolve dbt's ref()/source()/config() into plain DuckDB-qualified names."""
    sql = _CONFIG_RE.sub("", raw_sql)
    sql = _REF_RE.sub(lambda m: f"main.{m.group(1)}", sql)
    sql = _SOURCE_RE.sub(lambda m: f"{m.group(1)}.{m.group(2)}", sql)
    return sql.strip()


def build_models(warehouse_path: str | None = None) -> None:
    """Materialize every model into the warehouse in dependency order."""
    path = warehouse_path or str(WAREHOUSE_PATH)
    con = duckdb.connect(path)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS main")
        for name, folder, materialization in MODELS:
            sql_path = DBT_MODELS_DIR / folder / f"{name}.sql"
            body = render_sql(sql_path.read_text())
            keyword = "TABLE" if materialization == "table" else "VIEW"
            con.execute(f"CREATE OR REPLACE {keyword} main.{name} AS\n{body}")
            print(f"[transform] built {materialization:5s} main.{name}")
    finally:
        con.close()


def run_checks(warehouse_path: str | None = None) -> None:
    """Run the data-quality checks; raise if any fails."""
    path = warehouse_path or str(WAREHOUSE_PATH)
    con = duckdb.connect(path, read_only=True)
    failures: list[str] = []
    try:
        for label, query in CHECKS:
            failing = con.execute(query).fetchone()[0]
            status = "PASS" if failing == 0 else f"FAIL ({failing})"
            print(f"[test] {status:12s} {label}")
            if failing != 0:
                failures.append(label)
    finally:
        con.close()
    if failures:
        raise SystemExit(f"\n{len(failures)} data-quality check(s) failed: {failures}")
    print(f"[test] all {len(CHECKS)} checks passed")


if __name__ == "__main__":
    build_models()
    run_checks()
