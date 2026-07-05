"""Pull macroeconomic series from the FRED API into a raw parquet file.

Each series is fetched independently and stacked into one long table
(series_id, date, value). FRED returns missing observations as the string '.',
which we keep as-is here and clean in staging.
"""
from __future__ import annotations

import sys

import httpx
import pandas as pd

from ingest.config import (
    FRED_API_KEY,
    FRED_BASE,
    FRED_SERIES,
    OBSERVATION_START,
    RAW_DIR,
)


def fetch_series(series_id: str, client: httpx.Client) -> pd.DataFrame:
    """Return a long frame of observations for one FRED series."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": OBSERVATION_START,
    }
    resp = client.get(FRED_BASE, params=params, timeout=30.0)
    resp.raise_for_status()
    observations = resp.json().get("observations", [])
    frame = pd.DataFrame(observations)
    if frame.empty:
        return pd.DataFrame(columns=["series_id", "label", "date", "value"])
    frame = frame[["date", "value"]].copy()
    frame["series_id"] = series_id
    frame["label"] = FRED_SERIES[series_id]
    return frame[["series_id", "label", "date", "value"]]


def ingest_fred() -> str:
    """Pull every configured series, write data/raw/fred_macro.parquet, return path."""
    if not FRED_API_KEY:
        sys.exit(
            "FRED_API_KEY is not set. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and put it in .env"
        )

    frames: list[pd.DataFrame] = []
    with httpx.Client() as client:
        for series_id in FRED_SERIES:
            print(f"[fred] fetching {series_id} ({FRED_SERIES[series_id]})")
            frame = fetch_series(series_id, client)
            print(f"[fred]   -> {len(frame):,} observations")
            frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    out_path = RAW_DIR / "fred_macro.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"[fred] wrote {len(combined):,} rows -> {out_path}")
    return str(out_path)


if __name__ == "__main__":
    ingest_fred()
