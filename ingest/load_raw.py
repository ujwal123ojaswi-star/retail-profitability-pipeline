"""Land the raw parquet files into a DuckDB `raw` schema.

dbt (via dbt-duckdb) reads from this same warehouse.duckdb file, so loading and
transformation share one database. Connections are opened and closed
sequentially because DuckDB allows a single writer.
"""
from __future__ import annotations

import duckdb

from ingest.config import RAW_DIR, WAREHOUSE_PATH

RAW_TABLES = {
    "sec_financials": RAW_DIR / "sec_financials.parquet",
    "fred_macro": RAW_DIR / "fred_macro.parquet",
}


def load_raw() -> None:
    """(Re)create raw.* tables in the warehouse from the parquet files on disk."""
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for table, path in RAW_TABLES.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing raw file {path}. Run the ingestion step first."
                )
            con.execute(
                f"CREATE OR REPLACE TABLE raw.{table} AS "
                "SELECT * FROM read_parquet(?)",
                [str(path)],
            )
            n = con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
            print(f"[load] raw.{table}: {n:,} rows")
    finally:
        con.close()


if __name__ == "__main__":
    load_raw()
