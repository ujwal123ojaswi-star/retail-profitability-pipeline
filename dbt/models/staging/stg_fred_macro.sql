-- Clean the FRED long table, drop the '.' missing-value sentinel, average each
-- series to a quarterly value, and pivot to one wide row per quarter so the
-- intermediate layer can join macro context on quarter_start.

with src as (
    select * from {{ source('raw', 'fred_macro') }}
),

cleaned as (
    select
        series_id,
        try_cast(date as date)  as obs_date,
        try_cast(value as double) as value
    from src
    where value is not null
      and value <> '.'            -- FRED missing-observation sentinel
),

quarterly as (
    select
        series_id,
        date_trunc('quarter', obs_date) as quarter_start,
        avg(value)                      as value
    from cleaned
    group by 1, 2
)

select
    quarter_start,
    max(value) filter (where series_id = 'CPIAUCSL') as cpi,
    max(value) filter (where series_id = 'RSXFS')    as retail_sales,
    max(value) filter (where series_id = 'UMCSENT')  as consumer_sentiment,
    max(value) filter (where series_id = 'UNRATE')   as unemployment,
    max(value) filter (where series_id = 'FEDFUNDS') as fed_funds
from quarterly
group by quarter_start
