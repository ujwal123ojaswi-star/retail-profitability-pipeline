"""Ingestion + warehouse sanity checks.

These skip automatically until you've run the pipeline, so the suite is green on
a fresh clone and meaningful after a build.
"""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
WAREHOUSE = PROJECT_ROOT / "data" / "warehouse.duckdb"


@pytest.mark.skipif(not (RAW_DIR / "sec_financials.parquet").exists(),
                    reason="run ingestion first")
def test_sec_raw_has_both_companies():
    import pandas as pd

    df = pd.read_parquet(RAW_DIR / "sec_financials.parquet")
    assert set(df["company_id"].unique()) >= {"WMT", "TGT"}
    assert len(df) > 0


@pytest.mark.skipif(not (RAW_DIR / "fred_macro.parquet").exists(),
                    reason="run ingestion first")
def test_fred_raw_has_all_series():
    import pandas as pd

    df = pd.read_parquet(RAW_DIR / "fred_macro.parquet")
    assert set(df["series_id"].unique()) >= {
        "RSXFS", "CPIAUCSL", "UMCSENT", "UNRATE", "FEDFUNDS"
    }


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="run dbt build first")
def test_fct_profitability_grain_is_unique():
    import duckdb

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        total, distinct = con.execute(
            "select count(*), count(distinct profitability_id) from fct_profitability"
        ).fetchone()
    finally:
        con.close()
    assert total == distinct, "profitability_id is not unique at the row grain"


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="run dbt build first")
def test_margins_within_sane_band():
    import duckdb

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        bad = con.execute(
            "select count(*) from fct_profitability "
            "where gross_margin is not null and (gross_margin < -1 or gross_margin > 1)"
        ).fetchone()[0]
    finally:
        con.close()
    assert bad == 0
