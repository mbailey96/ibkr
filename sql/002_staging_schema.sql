create schema if not exists staging;

drop table if exists staging.ibkr_benchmark_return;
drop table if exists staging.ibkr_position_snapshot;
drop table if exists staging.ibkr_key_statistics;
drop table if exists staging.ibkr_account_period_performance;
drop table if exists staging.ibkr_corporate_action;
drop table if exists staging.ibkr_interest;
drop table if exists staging.ibkr_cash_transaction;
drop table if exists staging.ibkr_trade;

create table if not exists staging.ibkr_trade (
    report_id uuid not null,
    transaction_id text primary key,
    trade_id text,
    account_id text,
    trade_datetime timestamp,
    trade_date date,
    settle_date date,
    symbol text,
    description text,
    isin text,
    asset_class text,
    buy_sell text,
    quantity numeric,
    trade_price numeric,
    trade_money numeric,
    proceeds numeric,
    taxes numeric,
    ib_commission numeric,
    net_cash numeric,
    cost_basis numeric,
    fifo_pnl_realized numeric,
    mtm_pnl numeric,
    currency text,
    exchange text,
    order_type text
);

create table if not exists staging.ibkr_cash_transaction (
    report_id uuid not null,
    transaction_id text primary key,
    account_id text,
    cash_datetime timestamp,
    cash_date date,
    settle_date date,
    currency text,
    amount numeric,
    type text,
    description text,
    symbol text,
    isin text,
    trade_id text,
    client_reference text
);

create table if not exists staging.ibkr_interest (
    report_id uuid not null,
    source_row_hash text not null,
    account_id text not null,
    report_date date,
    value_date date,
    currency text,
    interest_type text,
    total_principal numeric,
    rate numeric,
    total_interest numeric,
    code text,
    primary key (source_row_hash)
);

create table if not exists staging.ibkr_corporate_action (
    report_id uuid not null,
    corporate_action_id text primary key,
    transaction_id text,
    account_id text,
    report_date date,
    action_datetime timestamp,
    symbol text,
    isin text,
    action_description text,
    amount numeric,
    proceeds numeric,
    value numeric,
    quantity numeric,
    cost_basis numeric,
    type text
);

create table if not exists staging.ibkr_account_period_performance (
    report_id uuid not null,
    account_id text not null,
    name text,
    period_start date,
    period_end date,
    beginning_nav numeric,
    ending_nav numeric,
    period_return numeric,
    deposits numeric,
    withdrawals numeric,
    dividends numeric,
    interest numeric,
    fees numeric,
    primary key (account_id, period_start, period_end)
);

create table if not exists staging.ibkr_key_statistics (
    report_id uuid not null,
    period_start date,
    period_end date,
    beginning_nav numeric,
    ending_nav numeric,
    period_return numeric,
    one_month_return numeric,
    three_month_return numeric,
    mtm numeric,
    deposits_withdrawals numeric,
    dividends numeric,
    interest numeric,
    fees_commissions numeric,
    other numeric,
    change_in_nav numeric,
    primary key (period_start, period_end)
);

create table if not exists staging.ibkr_position_snapshot (
    position_snapshot_id text primary key,
    report_id uuid not null,
    as_of_date date,
    financial_instrument text,
    currency text,
    symbol text,
    description text,
    sector text,
    quantity numeric,
    close_price numeric,
    market_value numeric,
    cost_basis numeric,
    unrealized_pnl numeric,
    fx_rate_to_base numeric,
    is_total boolean not null default false
);

create table if not exists staging.ibkr_benchmark_return (
    report_id uuid not null,
    period_type text not null,
    period_label text not null,
    bm1 text,
    bm1_return numeric,
    bm2 text,
    bm2_return numeric,
    account text,
    account_return numeric,
    primary key (period_type, period_label, account)
);
