-- The fact the dashboard reads: company x quarter grain, every margin + growth +
-- macro column, plus company metadata. A surrogate key supports a clean
-- uniqueness test on the grain.

with metrics as (
    select * from {{ ref('int_quarterly_metrics') }}
),

company as (
    select * from {{ ref('dim_company') }}
)

select
    m.company_id || '-' || cast(m.quarter_start as varchar) as profitability_id,
    m.company_id,
    c.company_name,
    c.ticker,
    c.strategy,
    m.quarter_start,
    m.year,
    m.quarter,
    m.revenue,
    m.cost_of_revenue,
    m.gross_profit,
    m.operating_income,
    m.net_income,
    m.assets,
    m.liabilities,
    m.gross_margin,
    m.operating_margin,
    m.net_margin,
    m.revenue_yoy,
    m.cpi,
    m.retail_sales,
    m.consumer_sentiment,
    m.unemployment,
    m.fed_funds
from metrics m
join company c on m.company_id = c.company_id
