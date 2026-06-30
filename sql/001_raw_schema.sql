create schema if not exists raw;

drop table if exists raw.ibkr_flex_row;
drop table if exists raw.ibkr_portfolio_summary_row;

create table if not exists raw.report_file (
    report_id uuid primary key,
    source_system text not null,
    report_type text not null,
    account_id text,
    period_start date,
    period_end date,
    generated_at timestamptz,
    ingested_at timestamptz not null default now(),
    original_filename text not null,
    stored_file_path text not null,
    file_sha256 text not null unique,
    parser_version text not null,
    row_count integer,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists raw.pipeline_run (
    run_id uuid primary key,
    source_system text not null,
    status text not null,
    started_at timestamptz not null,
    finished_at timestamptz not null,
    downloaded_files integer not null default 0,
    ingested_files integer not null default 0,
    skipped_files integer not null default 0,
    validation_message_count integer not null default 0
);

delete from raw.report_file
where source_system = 'ibkr'
  and report_type <> 'flex_statement';

create table if not exists raw.ibkr_flex_statement_row (
    report_id uuid not null references raw.report_file(report_id),
    row_number integer not null,
    account_id text,
    section_code text not null,
    section_name text,
    raw_payload jsonb not null,
    primary key (report_id, row_number)
);

create index if not exists idx_report_file_type_ingested
    on raw.report_file(report_type, ingested_at desc);

create index if not exists idx_ibkr_flex_statement_section
    on raw.ibkr_flex_statement_row(section_code, account_id);
