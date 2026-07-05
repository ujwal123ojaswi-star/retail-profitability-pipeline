"""One command to build the whole warehouse end to end -- no dbt, no Prefect.

    python build.py

Runs: SEC ingestion -> FRED ingestion -> load raw into DuckDB ->
transform (staging -> intermediate -> marts) -> data-quality checks.
Then launch the dashboard with:  streamlit run app/dashboard.py
"""
from __future__ import annotations

from ingest.fred import ingest_fred
from ingest.load_raw import load_raw
from ingest.sec import ingest_sec
from transform import build_models, run_checks


def main() -> None:
    print("==> [1/5] Ingesting SEC EDGAR financials")
    ingest_sec()

    print("\n==> [2/5] Ingesting FRED macro series")
    ingest_fred()

    print("\n==> [3/5] Loading raw parquet into DuckDB")
    load_raw()

    print("\n==> [4/5] Transforming (staging -> intermediate -> marts)")
    build_models()

    print("\n==> [5/5] Running data-quality checks")
    run_checks()

    print("\nDone. Launch the dashboard with:")
    print("    streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
