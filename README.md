# Retail Profitability Pipeline

**Live dashboard:** _<add your Streamlit Community Cloud URL here once deployed>_

> Does **cost leadership** (Walmart) or **differentiation** (Target) produce more
> durable margins across the economic cycle? This pipeline ingests a decade of SEC
> filings and FRED macro data, transforms it in a warehouse, and serves the answer
> as an interactive dashboard. **Headline finding:** Walmart runs structurally
> thinner gross margins but holds them roughly **[3–5] percentage points** steadier
> than Target through demand and inflation shocks (fill in the real number from your run).

## Architecture

```
SEC EDGAR (XBRL)  ─┐
                   ├─►  ingest/ (httpx + pandas) ─►  data/raw/*.parquet
FRED (macro API)  ─┘                                      │
                                                          ▼
                                          DuckDB  raw schema  (ingest/load_raw.py)
                                                          │
                                                          ▼
                                   dbt-duckdb:  staging ─► intermediate ─► marts
                                          (cast/classify) (coalesce, margins) (fct/dim + tests)
                                                          │
                                                          ▼
                                       Streamlit dashboard  (app/dashboard.py)
                                                          │
                                                          ▼
                          optional NL→SQL query layer  (app/llm_query.py, guardrailed)

Orchestrated end-to-end as a scheduled Prefect flow (flows/pipeline_flow.py).
```

## Stack

Python 3.11 · httpx · pandas · DuckDB · dbt-duckdb · Prefect · Streamlit · Plotly · Anthropic API (optional)

## Data sources

- **SEC EDGAR** company-facts XBRL API (`data.sec.gov`) for Walmart (CIK `0000104169`)
  and Target (CIK `0000027419`). Requires a descriptive `User-Agent`. The ingestion
  pulls multiple candidate `us-gaap` concept tags per metric and coalesces them, because
  companies change tags across years.
- **FRED** for the macro backdrop: retail sales (`RSXFS`), CPI (`CPIAUCSL`), consumer
  sentiment (`UMCSENT`), unemployment (`UNRATE`), fed funds (`FEDFUNDS`). Free API key required.

## Run it locally

```bash
# 1. environment
python -m venv .venv
.venv\Scripts\activate            # Windows  (use: source .venv/bin/activate on Mac/Linux)
pip install -e .

# 2. credentials
copy .env.example .env            # Windows  (use: cp on Mac/Linux)
#   then set SEC_USER_AGENT (your name + email) and FRED_API_KEY

# 3. build the warehouse end to end (ingest -> load -> transform -> checks)
python build.py

# 4. dashboard
streamlit run app/dashboard.py
```

`build.py` runs the whole pipeline in one command and prints PASS/FAIL for each
data-quality check at the end.

### A note on dbt and Python 3.14

dbt is the canonical transformation layer here and the `dbt/` project is the
real deliverable (recruiters read those models). However, **dbt does not yet
support Python 3.14**, so `build.py` ships a small runner (`transform.py`) that
executes the exact same `.sql` models directly against DuckDB and runs the same
data-quality checks — no dbt needed. On Python 3.11–3.13 you can use real dbt
instead:

```bash
pip install -e ".[dbt]"
cd dbt && dbt deps && dbt build --profiles-dir .
```

Optional scheduled orchestration (Prefect, also Python 3.11–3.13):
`pip install -e ".[orchestration]"` then `python flows/pipeline_flow.py`.

## dbt models

| Layer | Model | What it does |
|---|---|---|
| staging | `stg_sec_financials` | cast, classify each fact by period length, standardize to quarter |
| staging | `stg_fred_macro` | clean, resample to quarterly, pivot series wide |
| intermediate | `int_quarterly_metrics` | coalesce concept tags, pivot metrics wide, compute margins + YoY, join macro |
| marts | `fct_profitability` | company × quarter fact with surrogate key (dashboard reads this) |
| marts | `dim_company` | company metadata + strategy label |

Data-quality tests: `not_null` / `unique` on grain keys, `relationships` from fact to dim,
`accepted_values` on strategy, and `accepted_range` (−1..1) on margins.

## Known wrinkle (and why it's here)

Standalone quarterly income-statement figures come from the ~90-day periods in 10-Q
filings, which cleanly yield Q1–Q3. The fourth standalone quarter is not always tagged
directly; reconciling it from the annual 10-K minus year-to-date is left as a documented
follow-up in `int_quarterly_metrics.sql`. Surfacing real-data messiness rather than hiding
it is intentional — it's the point of the project.

## Optional: natural-language query layer

With `ANTHROPIC_API_KEY` set, the dashboard shows an "ask a question" box. It sends the
`fct_profitability` schema to the model, gets back a single DuckDB `SELECT`, validates it
with a read-only guardrail (`app/sql_guardrail.py` — rejects anything that isn't one
`SELECT`/`WITH` statement or that contains a mutating verb), runs it read-only, and phrases
the answer. The guardrail is unit-tested in `tests/test_sql_guardrail.py`.
