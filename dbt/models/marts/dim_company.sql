-- Company dimension: metadata plus the strategy label that frames the whole
-- analysis (Walmart = cost leadership, Target = differentiation).

select
    company_id,
    company_name,
    cik,
    ticker,
    strategy
from (
    values
        ('WMT', 'Walmart Inc.',       '0000104169', 'WMT', 'cost leadership'),
        ('TGT', 'Target Corporation', '0000027419', 'TGT', 'differentiation')
) as t(company_id, company_name, cik, ticker, strategy)
