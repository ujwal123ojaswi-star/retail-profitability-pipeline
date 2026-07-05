"""Pull company financial facts from SEC EDGAR (XBRL) into a raw parquet file.

The interesting part here is concept coalescing: the same economic metric
(e.g. revenue) is tagged under different us-gaap concepts across filings and
years. We pull every candidate concept that exists and tag each row with the
clean metric name plus a priority rank, then let the dbt layer pick the
preferred tag per company-quarter. Handling that messiness is the whole point.
"""
from __future__ import annotations

import time

import httpx
import pandas as pd

from ingest.config import (
    COMPANIES,
    METRIC_CONCEPTS,
    RAW_DIR,
    SEC_BASE,
    SEC_USER_AGENT,
)

# SEC asks for <= 10 requests/second. We make far fewer; this is polite spacing.
REQUEST_PAUSE_SECONDS = 0.3


def fetch_company_facts(cik: str, client: httpx.Client) -> dict:
    """Return the full company-facts JSON blob for a 10-digit zero-padded CIK."""
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    resp = client.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _extract_concept(facts_json: dict, concept: str) -> list[dict]:
    """Return all USD-denominated observations for a single us-gaap concept."""
    node = facts_json.get("facts", {}).get("us-gaap", {}).get(concept)
    if not node:
        return []
    rows: list[dict] = []
    for unit, entries in node.get("units", {}).items():
        if unit != "USD":
            continue
        for e in entries:
            rows.append(
                {
                    "concept": concept,
                    "unit": unit,
                    "start": e.get("start"),  # None for instant (balance-sheet) facts
                    "end": e.get("end"),
                    "val": e.get("val"),
                    "fy": e.get("fy"),
                    "fp": e.get("fp"),
                    "form": e.get("form"),
                    "filed": e.get("filed"),
                    "frame": e.get("frame"),
                }
            )
    return rows


def build_company_frame(company: dict, facts_json: dict) -> pd.DataFrame:
    """Flatten one company's facts into a long table tagged with clean metrics."""
    records: list[dict] = []
    for metric, candidates in METRIC_CONCEPTS.items():
        for priority, concept in enumerate(candidates):
            for row in _extract_concept(facts_json, concept):
                row.update(
                    {
                        "company_id": company["company_id"],
                        "company_name": company["company_name"],
                        "cik": company["cik"],
                        "metric": metric,
                        "concept_priority": priority,
                    }
                )
                records.append(row)
    return pd.DataFrame.from_records(records)


def ingest_sec() -> str:
    """Pull all companies, write data/raw/sec_financials.parquet, return its path."""
    frames: list[pd.DataFrame] = []
    with httpx.Client() as client:
        for company in COMPANIES:
            print(f"[sec] fetching {company['company_id']} (CIK {company['cik']})")
            facts = fetch_company_facts(company["cik"], client)
            frame = build_company_frame(company, facts)
            print(f"[sec]   -> {len(frame):,} raw concept rows")
            frames.append(frame)
            time.sleep(REQUEST_PAUSE_SECONDS)

    combined = pd.concat(frames, ignore_index=True)
    out_path = RAW_DIR / "sec_financials.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"[sec] wrote {len(combined):,} rows -> {out_path}")
    return str(out_path)


if __name__ == "__main__":
    ingest_sec()
