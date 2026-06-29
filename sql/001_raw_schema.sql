create schema if not exists raw;

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

create table if not exists raw.ibkr_flex_row (
    report_id uuid not null references raw.report_file(report_id),
    report_type text not null,
    row_number integer not null,
    raw_payload jsonb not null,
    primary key (report_id, row_number)
);

create table if not exists raw.ibkr_portfolio_summary_row (
    report_id uuid not null references raw.report_file(report_id),
    row_number integer not null,
    section text,
    row_type text,
    raw_values jsonb not null,
    primary key (report_id, row_number)
);

create index if not exists idx_report_file_type_ingested
    on raw.report_file(report_type, ingested_at desc);

create index if not exists idx_ibkr_flex_row_type
    on raw.ibkr_flex_row(report_type);

create index if not exists idx_ibkr_summary_section
    on raw.ibkr_portfolio_summary_row(section);

