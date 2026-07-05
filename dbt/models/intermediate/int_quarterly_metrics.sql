-- The core transformation. Three jobs:
--   1. Coalesce competing concept tags down to one value per metric per quarter
--      (preferring the highest-priority tag, then the most recently filed value).
--   2. Pivot the long metric table wide to one row per company-quarter.
--   3. Derive margins and YoY growth, and attach the macro overlay.
--
-- Note on grain: income-statement (flow) metrics use the standalone ~90-day
-- 10-Q periods, which cleanly give Q1-Q3. Q4 standalone is not always tagged
-- directly; reconciling it from the annual 10-K minus YTD is a known wrinkle and
-- left as a documented follow-up (see README). Balance-sheet metrics use the
-- point-in-time 'instant' facts.

with stg as (
    select * from {{ ref('stg_sec_financials') }}
),

-- one row per company / quarter / metric / period_type
deduped as (
    select *
    from stg
    qualify row_number() over (
        partition by company_id, quarter_start, metric, period_type
        order by concept_priority asc, filed desc
    ) = 1
),

flow_quarterly as (
    select company_id, quarter_start, metric, value
    from deduped
    where period_type = 'quarter'
      and metric in ('revenue', 'cost_of_revenue', 'gross_profit',
                     'operating_income', 'net_income')
),

balance as (
    select company_id, quarter_start, metric, value
    from deduped
    where period_type = 'instant'
      and metric in ('assets', 'liabilities')
),

long_facts as (
    select * from flow_quarterly
    union all
    select * from balance
),

wide as (
    select
        company_id,
        quarter_start,
        max(value) filter (where metric = 'revenue')          as revenue,
        max(value) filter (where metric = 'cost_of_revenue')  as cost_of_revenue,
        max(value) filter (where metric = 'gross_profit')     as gross_profit_reported,
        max(value) filter (where metric = 'operating_income') as operating_income,
        max(value) filter (where metric = 'net_income')       as net_income,
        max(value) filter (where metric = 'assets')           as assets,
        max(value) filter (where metric = 'liabilities')      as liabilities
    from long_facts
    group by 1, 2
),

macro as (
    select * from {{ ref('stg_fred_macro') }}
),

final as (
    select
        w.company_id,
        w.quarter_start,
        cast(year(w.quarter_start) as integer)    as year,
        cast(quarter(w.quarter_start) as integer) as quarter,

        w.revenue,
        w.cost_of_revenue,
        -- prefer the reported gross profit; otherwise derive it
        coalesce(w.gross_profit_reported, w.revenue - w.cost_of_revenue) as gross_profit,
        w.operating_income,
        w.net_income,
        w.assets,
        w.liabilities,

        -- margins, guarded against divide-by-zero / missing revenue
        case when w.revenue > 0
             then coalesce(w.gross_profit_reported, w.revenue - w.cost_of_revenue) / w.revenue
        end as gross_margin,
        case when w.revenue > 0 then w.operating_income / w.revenue end as operating_margin,
        case when w.revenue > 0 then w.net_income / w.revenue end       as net_margin,

        -- year-over-year revenue growth: same company, four quarters back
        w.revenue
            / nullif(lag(w.revenue, 4) over (
                  partition by w.company_id order by w.quarter_start), 0)
            - 1 as revenue_yoy,

        -- macro overlay
        m.cpi,
        m.retail_sales,
        m.consumer_sentiment,
        m.unemployment,
        m.fed_funds
    from wide w
    left join macro m on w.quarter_start = m.quarter_start
)

select * from final
