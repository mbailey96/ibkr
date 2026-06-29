select * from analytics.v_portfolio_latest;

select *
from analytics.v_positions_latest
order by market_value desc nulls last;

select *
from analytics.v_asset_allocation_latest
order by market_value desc nulls last;

select *
from analytics.v_trade_history
order by trade_date desc nulls last;

select *
from analytics.v_cashflow_history
order by cash_date desc nulls last;

select
    report_type,
    original_filename,
    row_count,
    ingested_at,
    stored_file_path
from raw.report_file
order by ingested_at desc;
