"""Retail profitability dashboard.

Reads fct_profitability from the DuckDB warehouse and presents a problem-first
view: KPIs, the headline WMT-TGT margin gap, growth comparison, a macro overlay,
a written takeaway, and an optional natural-language query box.

Run locally:   streamlit run app/dashboard.py
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from app.theme import THEME_CSS, apply_plotly_theme, plotly_chart

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_PATH = str(PROJECT_ROOT / "data" / "warehouse.duckdb")

MACRO_LABELS = {
    "cpi": "CPI (CPIAUCSL)",
    "retail_sales": "Retail sales (RSXFS)",
    "consumer_sentiment": "Consumer sentiment (UMCSENT)",
    "unemployment": "Unemployment (UNRATE)",
    "fed_funds": "Fed funds rate (FEDFUNDS)",
}

st.set_page_config(page_title="Retail Profitability: Cost Leadership vs Differentiation",
                   layout="wide")
apply_plotly_theme(pio)
st.markdown(THEME_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    con = duckdb.connect(WAREHOUSE_PATH, read_only=True)
    try:
        df = con.execute(
            "select * from fct_profitability order by company_id, quarter_start"
        ).fetch_df()
    finally:
        con.close()
    df["quarter_start"] = pd.to_datetime(df["quarter_start"])
    df["quarter_label"] = df["year"].astype(str) + " Q" + df["quarter"].astype(str)
    return df


def kpi_row(df: pd.DataFrame) -> None:
    cols = st.columns(2)
    for col, company_id in zip(cols, ["WMT", "TGT"]):
        sub = df[df["company_id"] == company_id].sort_values("quarter_start")
        if sub.empty:
            continue
        latest = sub.iloc[-1]
        prior = sub[sub["quarter"] == latest["quarter"]]
        prior = prior[prior["year"] == latest["year"] - 1]
        with col:
            st.subheader(f"{latest['company_name']}  ·  {latest['strategy']}")
            a, b, c = st.columns(3)
            rev_b = (latest["revenue"] or 0) / 1e9
            a.metric("Revenue (latest qtr)", f"${rev_b:,.1f}B")
            gm = latest["gross_margin"]
            b.metric("Gross margin", f"{gm:.1%}" if pd.notna(gm) else "n/a")
            om = latest["operating_margin"]
            c.metric("Operating margin", f"{om:.1%}" if pd.notna(om) else "n/a")
            if not prior.empty:
                yoy = latest["revenue_yoy"]
                if pd.notna(yoy):
                    st.caption(f"Revenue YoY: {yoy:+.1%}")


def margin_gap_chart(df: pd.DataFrame, margin_col: str) -> None:
    wide = df.pivot_table(index="quarter_start", columns="company_id",
                          values=margin_col, aggfunc="first")
    if "WMT" not in wide or "TGT" not in wide:
        st.info("Need both companies present to compute the gap.")
        return
    gap = (wide["WMT"] - wide["TGT"]).dropna().reset_index()
    gap.columns = ["quarter_start", "margin_gap"]
    fig = px.area(gap, x="quarter_start", y="margin_gap",
                  title=f"Margin gap (Walmart − Target), {margin_col.replace('_', ' ')}")
    fig.add_hline(y=0, line_dash="dot")
    fig.update_yaxes(tickformat=".1%", title="WMT − TGT")
    fig.update_xaxes(title="Quarter")
    plotly_chart(fig, use_container_width=True)
    if not gap.empty:
        widest = gap.loc[gap["margin_gap"].abs().idxmax()]
        st.caption(
            f"Widest gap: {widest['margin_gap']:+.1%} in "
            f"{pd.to_datetime(widest['quarter_start']):%Y Q%q}".replace("%q", "")
        )


def margin_lines(df: pd.DataFrame, margin_col: str) -> None:
    fig = px.line(df, x="quarter_start", y=margin_col, color="company_name",
                  title=f"{margin_col.replace('_', ' ').title()} over time")
    fig.update_yaxes(tickformat=".1%", title="Margin")
    fig.update_xaxes(title="Quarter")
    plotly_chart(fig, use_container_width=True)


def macro_overlay(df: pd.DataFrame, margin_col: str, macro_col: str) -> None:
    fig = go.Figure()
    for company_id in ["WMT", "TGT"]:
        sub = df[df["company_id"] == company_id].sort_values("quarter_start")
        fig.add_trace(go.Scatter(x=sub["quarter_start"], y=sub[margin_col],
                                 name=f"{company_id} {margin_col.replace('_', ' ')}",
                                 yaxis="y1"))
    macro = df.drop_duplicates("quarter_start").sort_values("quarter_start")
    fig.add_trace(go.Scatter(x=macro["quarter_start"], y=macro[macro_col],
                             name=MACRO_LABELS.get(macro_col, macro_col),
                             line=dict(dash="dot"), yaxis="y2"))
    fig.update_layout(
        title=f"Margins vs {MACRO_LABELS.get(macro_col, macro_col)}",
        yaxis=dict(title="Margin", tickformat=".0%"),
        yaxis2=dict(title=MACRO_LABELS.get(macro_col, macro_col),
                    overlaying="y", side="right"),
        legend=dict(orientation="h", y=-0.2),
    )
    plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.title("Cost leadership vs differentiation: which produces more durable retail margins?")
    st.markdown(
        "Comparing **Walmart** (cost leadership) and **Target** (differentiation) on "
        "quarterly profitability over time, overlaid against the macro environment. "
        "Data: SEC EDGAR XBRL filings + FRED macro series."
    )

    try:
        df = load_data()
    except Exception as exc:  # noqa: BLE001
        st.error(
            "Could not read the warehouse. Build it first by running "
            "`python build.py` from the project folder, then reload.\n\n"
            f"Detail: {exc}"
        )
        return

    # --- controls ---
    with st.sidebar:
        st.header("Controls")
        margin_col = st.selectbox(
            "Margin metric",
            ["operating_margin", "gross_margin", "net_margin"],
            format_func=lambda c: c.replace("_", " ").title(),
        )
        years = sorted(df["year"].dropna().unique())
        if years:
            lo, hi = st.select_slider("Year range", options=years,
                                      value=(years[0], years[-1]))
            df = df[(df["year"] >= lo) & (df["year"] <= hi)]
        macro_col = st.selectbox(
            "Macro overlay series",
            list(MACRO_LABELS.keys()),
            format_func=lambda c: MACRO_LABELS[c],
        )

    kpi_row(df)
    st.divider()
    margin_gap_chart(df, margin_col)
    col1, col2 = st.columns(2)
    with col1:
        margin_lines(df, margin_col)
    with col2:
        rev = df.copy()
        rev["revenue_b"] = rev["revenue"] / 1e9
        fig = px.line(rev, x="quarter_start", y="revenue_b", color="company_name",
                      title="Revenue over time ($B)")
        fig.update_xaxes(title="Quarter")
        fig.update_yaxes(title="Revenue ($B)")
        plotly_chart(fig, use_container_width=True)
    st.divider()
    macro_overlay(df, margin_col, macro_col)

    st.divider()
    st.subheader("Strategy takeaway")
    st.markdown(
        "Walmart's cost-leadership model runs structurally thinner gross margins "
        "but tends to hold them steadier when consumer demand softens or prices "
        "rise — the macro overlay is where that durability shows up. Target's "
        "differentiation supports richer margins in good quarters but is more "
        "exposed to discretionary pullbacks. Use the margin-gap chart above to "
        "read where each strategy gained or lost relative ground across the cycle."
    )

    # --- optional LLM box ---
    st.divider()
    st.subheader("Ask a question about the data")
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.caption("Set ANTHROPIC_API_KEY to enable the natural-language query box.")
        return
    question = st.text_input("e.g. which quarter had the widest operating-margin gap?")
    if question:
        from app.llm_query import ask  # deferred import

        with st.spinner("Translating to SQL and querying the warehouse..."):
            out = ask(question, WAREHOUSE_PATH)
        if not out["ok"]:
            st.error(f"Query rejected by guardrail: {out['reason']}")
            st.code(out["sql"], language="sql")
        else:
            st.success(out["answer"])
            with st.expander("Show SQL and result"):
                st.code(out["sql"], language="sql")
                st.dataframe(out["result"])


if __name__ == "__main__":
    main()
