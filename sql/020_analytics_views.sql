create schema if not exists analytics;

create or replace view analytics.v_portfolio_latest as
select
    ks.report_id,
    rf.original_filename,
    rf.ingested_at,
    ks.period_start,
    ks.period_end,
    ks.beginning_nav,
    ks.ending_nav,
    ks.period_return,
    ks.one_month_return,
    ks.three_month_return,
    ks.mtm,
    ks.deposits_withdrawals,
    ks.dividends,
    ks.interest,
    ks.fees_commissions,
    ks.other,
    ks.change_in_nav
from staging.ibkr_key_statistics ks
join raw.report_file rf on rf.report_id = ks.report_id
order by ks.period_end desc nulls last, rf.ingested_at desc
limit 1;

create or replace view analytics.v_positions_latest as
with latest_snapshot as (
    select report_id, as_of_date
    from staging.ibkr_position_snapshot
    where as_of_date is not null
    order by as_of_date desc, report_id desc
    limit 1
)
select p.*
from staging.ibkr_position_snapshot p
join latest_snapshot l
    on l.report_id = p.report_id
   and l.as_of_date = p.as_of_date
where p.is_total = false;

create or replace view analytics.v_asset_allocation_latest as
select
    financial_instrument,
    currency,
    sum(market_value) as market_value,
    sum(cost_basis) as cost_basis,
    sum(unrealized_pnl) as unrealized_pnl
from analytics.v_positions_latest
group by financial_instrument, currency;

create or replace view analytics.v_trade_history as
select *
from staging.ibkr_trade;

create or replace view analytics.v_cashflow_history as
select *
from staging.ibkr_cash_transaction;

create or replace view analytics.v_interest_history as
select *
from staging.ibkr_interest;

create or replace view analytics.v_benchmark_comparison as
select *
from staging.ibkr_benchmark_return;

create or replace view analytics.v_latest_refresh as
select
    max(rf.ingested_at) as last_updated_at,
    (select min(period_start) from staging.ibkr_key_statistics) as earliest_period_start,
    (select max(period_end) from staging.ibkr_key_statistics) as latest_period_end,
    max(rf.ingested_at) filter (where rf.report_type = 'portfolio_summary') as latest_portfolio_summary_at,
    max(rf.ingested_at) filter (where rf.report_type = 'flex_trades') as latest_trades_at,
    max(rf.ingested_at) filter (where rf.report_type = 'flex_cash') as latest_cash_at,
    max(rf.ingested_at) filter (where rf.report_type = 'flex_interest') as latest_interest_at,
    max(rf.ingested_at) filter (where rf.report_type = 'flex_statement') as latest_flex_statement_at,
    count(*) as source_file_count
from raw.report_file rf
where rf.source_system = 'ibkr';

create or replace view analytics.v_overview_kpis as
with latest as (
    select *
    from analytics.v_portfolio_latest
),
position_totals as (
    select
        coalesce(sum(market_value), 0) as position_value,
        coalesce(sum(market_value) filter (where financial_instrument = 'Cash'), 0) as cash_value,
        coalesce(sum(unrealized_pnl), 0) as unrealized_pnl
    from analytics.v_positions_latest
)
select
    latest.period_start,
    latest.period_end,
    latest.ending_nav as total_investable_assets,
    latest.one_month_return,
    latest.period_return as ytd_return,
    latest.period_return as since_inception_return,
    latest.deposits_withdrawals as total_contributions,
    latest.mtm as investment_return,
    latest.interest as interest_earned,
    latest.fees_commissions as fees_paid,
    latest.other as other_change,
    latest.change_in_nav,
    position_totals.unrealized_pnl,
    position_totals.cash_value,
    case
        when latest.ending_nav is null or latest.ending_nav = 0 then null
        else position_totals.cash_value / latest.ending_nav
    end as cash_weight,
    case
        when latest.change_in_nav is null or latest.change_in_nav = 0 then null
        else latest.deposits_withdrawals / latest.change_in_nav
    end as contribution_share_of_nav_change,
    case
        when latest.change_in_nav is null or latest.change_in_nav = 0 then null
        else latest.mtm / latest.change_in_nav
    end as investment_share_of_nav_change
from latest
cross join position_totals;

create or replace view analytics.v_portfolio_value_timeseries as
select
    period_end as as_of_date,
    ending_nav,
    deposits_withdrawals,
    mtm,
    interest,
    fees_commissions,
    change_in_nav
from staging.ibkr_key_statistics
where period_end is not null
order by period_end;

create or replace view analytics.v_monthly_growth_attribution as
select
    date_trunc('month', coalesce(cash_date, settle_date))::date as month_start,
    coalesce(sum(amount) filter (where type = 'Deposits/Withdrawals'), 0) as contributions,
    coalesce(sum(amount) filter (where type ilike '%Interest%'), 0) as interest,
    coalesce(sum(amount) filter (where type ilike '%Commission%'), 0) as fees,
    coalesce(sum(amount) filter (
        where type is not null
          and type <> 'Deposits/Withdrawals'
          and type not ilike '%Interest%'
          and type not ilike '%Commission%'
    ), 0) as other_cashflows
from staging.ibkr_cash_transaction
where coalesce(cash_date, settle_date) is not null
group by 1
order by 1;

create or replace view analytics.v_current_allocation_by_wrapper as
with latest_period as (
    select max(period_end) as period_end
    from staging.ibkr_account_period_performance
),
account_values as (
    select
        p.account_id,
        case
            when p.account_id = 'U24765593' then 'IBKR GIA'
            when p.account_id = 'U25245520' then 'IBKR ISA'
            else p.account_id
        end as wrapper,
        p.ending_nav as market_value
    from staging.ibkr_account_period_performance p
    join latest_period l on l.period_end = p.period_end
)
select
    account_id,
    wrapper,
    market_value,
    case
        when sum(market_value) over () = 0 then null
        else market_value / sum(market_value) over ()
    end as weight
from account_values;

create or replace view analytics.v_current_holdings as
select
    p.as_of_date,
    p.financial_instrument,
    p.currency,
    p.symbol,
    p.description,
    p.sector,
    p.quantity,
    p.close_price,
    p.market_value,
    p.cost_basis,
    p.unrealized_pnl,
    case
        when sum(p.market_value) over () = 0 then null
        else p.market_value / sum(p.market_value) over ()
    end as weight
from analytics.v_positions_latest p;

create or replace view analytics.v_performance_vs_benchmark as
select
    period_type,
    period_label,
    bm1,
    bm1_return,
    bm2,
    bm2_return,
    account,
    account_return,
    account_return - bm1_return as active_return_vs_bm1,
    account_return - bm2_return as active_return_vs_bm2
from analytics.v_benchmark_comparison;

create or replace view analytics.v_monthly_returns as
select
    period_label as month_label,
    bm1,
    bm1_return,
    bm2,
    bm2_return,
    account,
    account_return,
    account_return - bm1_return as active_return_vs_bm1
from analytics.v_benchmark_comparison
where period_type = 'month'
order by period_label;

create or replace view analytics.v_recent_trades as
select
    *,
    mtm_pnl as trade_pnl
from staging.ibkr_trade;

create or replace view analytics.v_recent_cashflows as
select *
from staging.ibkr_cash_transaction;

create or replace view analytics.v_trade_display as
select
    trade_datetime,
    case
        when account_id = 'U24765593' then 'GIA'
        when account_id = 'U25245520' then 'ISA'
        else account_id
    end as account,
    symbol,
    description,
    asset_class,
    buy_sell,
    quantity,
    trade_price,
    trade_money,
    ib_commission,
    net_cash,
    cost_basis,
    fifo_pnl_realized as realized_pnl,
    mtm_pnl as trade_pnl,
    currency
from staging.ibkr_trade;

create or replace view analytics.v_cashflow_display as
select
    cash_datetime,
    case
        when account_id = 'U24765593' then 'GIA'
        when account_id = 'U25245520' then 'ISA'
        else account_id
    end as account,
    type,
    description,
    symbol,
    amount,
    currency
from staging.ibkr_cash_transaction;

create or replace view analytics.v_interest_display as
select
    value_date,
    case
        when account_id = 'U24765593' then 'GIA'
        when account_id = 'U25245520' then 'ISA'
        else account_id
    end as account,
    interest_type,
    currency,
    total_principal,
    rate,
    total_interest
from staging.ibkr_interest;

create or replace view analytics.v_data_quality_checks as
with report_counts as (
    select report_type, count(*) as file_count, max(ingested_at) as latest_ingested_at
    from raw.report_file
    group by report_type
),
latest_nav as (
    select ending_nav
    from analytics.v_portfolio_latest
),
latest_positions as (
    select coalesce(sum(market_value), 0) as position_value
    from analytics.v_positions_latest
),
reconciliation as (
    select abs(coalesce(n.ending_nav, 0) - coalesce(p.position_value, 0)) as nav_position_difference
    from latest_nav n
    cross join latest_positions p
),
checks as (
    select
        'flex_statement_latest'::text as check_name,
        case when exists (select 1 from report_counts where report_type = 'flex_statement') then 'pass' else 'warning' end as status,
        coalesce((select file_count::text || ' file(s), latest at ' || latest_ingested_at::text from report_counts where report_type = 'flex_statement'), 'no sectioned flex statement files') as details
    union all
    select
        'portfolio_summary_latest'::text as check_name,
        case
            when exists (select 1 from report_counts where report_type in ('portfolio_summary', 'flex_statement')) then 'pass'
            else 'fail'
        end as status,
        coalesce(
            (select 'portfolio summary latest at ' || latest_ingested_at::text from report_counts where report_type = 'portfolio_summary'),
            (select 'sectioned flex latest at ' || latest_ingested_at::text from report_counts where report_type = 'flex_statement'),
            'no portfolio summary or sectioned flex files'
        ) as details
    union all
    select
        'flex_trades_latest',
        case when exists (select 1 from report_counts where report_type = 'flex_trades') then 'pass' else 'warning' end,
        coalesce((select file_count::text || ' file(s), latest at ' || latest_ingested_at::text from report_counts where report_type = 'flex_trades'), 'no trades files')
    union all
    select
        'flex_cash_latest',
        case when exists (select 1 from report_counts where report_type = 'flex_cash') then 'pass' else 'warning' end,
        coalesce((select file_count::text || ' file(s), latest at ' || latest_ingested_at::text from report_counts where report_type = 'flex_cash'), 'no cash files')
    union all
    select
        'flex_interest_latest',
        case when exists (select 1 from report_counts where report_type = 'flex_interest') then 'pass' else 'warning' end,
        coalesce((select file_count::text || ' file(s), latest at ' || latest_ingested_at::text from report_counts where report_type = 'flex_interest'), 'no interest files')
    union all
    select
        'nav_vs_positions',
        case when (select nav_position_difference from reconciliation) <= 1 then 'pass' else 'warning' end,
        'difference ' || (select nav_position_difference::text from reconciliation)
    union all
    select
        'missing_trade_account_ids',
        case when count(*) = 0 then 'pass' else 'warning' end,
        count(*)::text || ' trade row(s) missing account id'
    from staging.ibkr_trade
    where account_id is null
    union all
    select
        'null_trade_symbols',
        case when count(*) = 0 then 'pass' else 'warning' end,
        count(*)::text || ' trade row(s) missing symbol'
    from staging.ibkr_trade
    where symbol is null
)
select
    check_name,
    status,
    details,
    now() as checked_at
from checks;
