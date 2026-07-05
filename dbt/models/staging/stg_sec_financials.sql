-- Light cleaning only: cast types, standardize the period end to a quarter,
-- and classify each fact by the length of its reporting window. No business
-- logic and no coalescing yet -- that happens in the intermediate layer.

with src as (
    select * from {{ source('raw', 'sec_financials') }}
),

cleaned as (
    select
        company_id,
        company_name,
        cik,
        metric,
        concept,
        concept_priority,
        cast(val as double)        as value,
        try_cast("start" as date)  as period_start,
        try_cast("end" as date)    as period_end,
        fy,
        fp,
        form,
        try_cast(filed as date)    as filed,
        case
            when "start" is not null
            then date_diff('day', try_cast("start" as date), try_cast("end" as date))
        end as period_days
    from src
    where val is not null
      and "end" is not null
),

classified as (
    select
        *,
        date_trunc('quarter', period_end) as quarter_start,
        case
            when period_days is null                  then 'instant'   -- balance sheet
            when period_days between 80 and 100       then 'quarter'    -- standalone 10-Q
            when period_days between 170 and 195      then 'half'       -- 6-month YTD
            when period_days between 260 and 285      then 'ytd9'       -- 9-month YTD
            when period_days between 350 and 380      then 'annual'     -- full year 10-K
            else 'other'
        end as period_type
    from cleaned
)

select * from classified
