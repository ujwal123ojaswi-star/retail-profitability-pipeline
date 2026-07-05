"""Central configuration for the ingestion layer.

Everything that describes *what* to pull (companies, concepts, series) lives here
so the fetch code stays generic and the messy domain knowledge is in one place.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# --- SEC EDGAR ---------------------------------------------------------------
SEC_BASE = "https://data.sec.gov"
# SEC blocks generic user agents. Set SEC_USER_AGENT in your .env to
# "Your Name your-email@example.com".
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Retail Profitability Pipeline contact@example.com")

# company_id is the clean join key used through the whole warehouse.
# (cik must be the 10-digit zero-padded form used in the SEC URL.)
COMPANIES = [
    {"company_id": "WMT", "company_name": "Walmart Inc.", "cik": "0000104169", "ticker": "WMT"},
    {"company_id": "TGT", "company_name": "Target Corporation", "cik": "0000027419", "ticker": "TGT"},
]

# Each metric maps to an ordered list of candidate us-gaap concept tags.
# Companies switch tags over the years, so we pull every candidate that exists
# and let the transformation layer coalesce by priority (index 0 = preferred).
METRIC_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
}

# --- FRED --------------------------------------------------------------------
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# series_id -> human label (label is informational; series_id is the join key)
FRED_SERIES = {
    "RSXFS": "retail_sales",
    "CPIAUCSL": "cpi",
    "UMCSENT": "consumer_sentiment",
    "UNRATE": "unemployment",
    "FEDFUNDS": "fed_funds",
}

# How far back to pull. SEC company facts return full history regardless;
# this bounds the FRED pull.
OBSERVATION_START = os.getenv("OBSERVATION_START", "2013-01-01")
