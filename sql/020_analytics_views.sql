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

create or replace view analytics.v_latest_refresh as
select
    coalesce(
        (select max(finished_at) from raw.pipeline_run where source_system = 'ibkr' and status = 'success'),
        max(rf.ingested_at)
    ) as last_updated_at,
    (select min(period_start) from staging.ibkr_key_statistics) as earliest_period_start,
    (select max(period_end) from staging.ibkr_key_statistics) as latest_period_end,
    max(rf.ingested_at) filter (where rf.report_type = 'flex_statement') as latest_flex_statement_at,
    count(*) as source_file_count
from raw.report_file rf
where rf.source_system = 'ibkr';

create or replace view analytics.v_overview_kpis as
with latest as (
    select *
    from analytics.v_portfolio_latest
),
latest_daily_nav as (
    select
        as_of_date,
        sum(total) as total_nav
    from staging.ibkr_nav_snapshot
    group by as_of_date
    order by as_of_date desc
    limit 1
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
    coalesce(latest_daily_nav.total_nav, latest.ending_nav) as total_investable_assets,
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
left join latest_daily_nav on true
cross join position_totals;

create or replace view analytics.v_portfolio_value_timeseries as
select
    as_of_date,
    sum(total) as ending_nav,
    sum(cash) as cash,
    sum(stock) as stock,
    sum(funds) as funds,
    sum(options) as options,
    sum(bonds) as bonds,
    sum(coalesce(dividend_accruals, 0) + coalesce(interest_accruals, 0) + coalesce(fee_accruals, 0)) as accruals
from staging.ibkr_nav_snapshot
where as_of_date is not null
group by as_of_date
order by as_of_date;

create or replace view analytics.v_portfolio_value_by_account as
select
    as_of_date,
    case
        when account_id = 'U24765593' then 'GIA'
        when account_id = 'U25245520' then 'ISA'
        else account_id
    end as account,
    account_id,
    total as ending_nav,
    cash,
    stock,
    funds,
    options,
    bonds
from staging.ibkr_nav_snapshot
where as_of_date is not null
order by as_of_date, account;

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
        p.beginning_nav,
        p.ending_nav as market_value,
        p.period_return,
        p.deposits,
        p.dividends,
        p.interest,
        p.fees
    from staging.ibkr_account_period_performance p
    join latest_period l on l.period_end = p.period_end
)
select
    account_id,
    wrapper,
    beginning_nav,
    market_value,
    period_return,
    deposits,
    dividends,
    interest,
    fees,
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

create or replace view analytics.v_asset_performance_ytd as
with latest_holdings as (
    select
        account_id,
        symbol,
        description,
        max(financial_instrument) as financial_instrument,
        sum(market_value) as market_value,
        sum(unrealized_pnl) as unrealized_pnl,
        max(currency) as currency
    from analytics.v_positions_latest
    group by account_id, symbol, description
),
perf as (
    select
        account_id,
        symbol,
        description,
        max(asset_class) as asset_class,
        max(sub_category) as sub_category,
        sum(mtm_mtd) as mtm_mtd,
        sum(mtm_ytd) as mtm_ytd,
        sum(realized_pnl_mtd) as realized_pnl_mtd,
        sum(realized_pnl_ytd) as realized_pnl_ytd
    from staging.ibkr_symbol_performance
    group by account_id, symbol, description
)
select
    case
        when coalesce(perf.account_id, latest_holdings.account_id) = 'U24765593' then 'GIA'
        when coalesce(perf.account_id, latest_holdings.account_id) = 'U25245520' then 'ISA'
        else coalesce(perf.account_id, latest_holdings.account_id)
    end as account,
    coalesce(perf.symbol, latest_holdings.symbol) as symbol,
    coalesce(perf.description, latest_holdings.description) as description,
    coalesce(perf.asset_class, latest_holdings.financial_instrument) as asset_class,
    perf.sub_category,
    latest_holdings.market_value,
    case
        when sum(latest_holdings.market_value) over () = 0 then null
        else latest_holdings.market_value / sum(latest_holdings.market_value) over ()
    end as weight,
    latest_holdings.unrealized_pnl,
    perf.mtm_mtd,
    perf.mtm_ytd,
    perf.realized_pnl_mtd,
    perf.realized_pnl_ytd,
    coalesce(perf.mtm_ytd, 0) + coalesce(perf.realized_pnl_ytd, 0) as total_pnl_ytd
from perf
full outer join latest_holdings
    on latest_holdings.account_id = perf.account_id
   and coalesce(latest_holdings.symbol, '') = coalesce(perf.symbol, '')
   and coalesce(latest_holdings.description, '') = coalesce(perf.description, '')
where coalesce(perf.symbol, latest_holdings.symbol, perf.description, latest_holdings.description) is not null;

create or replace view analytics.v_asset_class_contribution as
select
    case
        when account_id = 'U24765593' then 'GIA'
        when account_id = 'U25245520' then 'ISA'
        else account_id
    end as account,
    asset_class,
    currency,
    prior_period_value,
    transactions,
    mtm_pnl_prior_period_positions,
    mtm_pnl_transactions,
    corporate_actions,
    other,
    account_transfers,
    linking_adjustments,
    fx_translation_pnl,
    future_price_adjustments,
    settled_cash,
    end_of_period_value,
    coalesce(mtm_pnl_prior_period_positions, 0) + coalesce(mtm_pnl_transactions, 0) as total_mtm_pnl
from staging.ibkr_asset_class_change;

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
