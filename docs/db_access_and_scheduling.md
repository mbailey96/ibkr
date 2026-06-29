# Operations

## Database Access

Postgres runs in Docker and is published on `localhost:55432`.

Use these DBeaver settings:

```text
Database type: PostgreSQL
Host: localhost
Port: 55432
Database: portfolio
Username: portfolio
Password: portfolio_dev_password
```

Useful schemas:

- `raw`: immutable source file registry and raw rows.
- `staging`: typed IBKR tables.
- `analytics`: views used by Dash and reconciliation.

Starter queries:

```sql
select * from analytics.v_portfolio_latest;
select * from analytics.v_positions_latest order by market_value desc nulls last;
select * from analytics.v_trade_history order by trade_date desc nulls last;
select * from analytics.v_cashflow_history order by cash_date desc nulls last;

select report_type, original_filename, row_count, ingested_at
from raw.report_file
order by ingested_at desc;
```

## Scheduled Pipeline

Run the full pipeline manually:

```bash
cd /Users/mbailey/personal/portfolio-warehouse
make PYTHON=/Users/mbailey/opt/anaconda3/envs/py311/bin/python run-pipeline
```

That command:

1. Fetches the configured IBKR source into `data/inbox`.
2. Ingests inbox CSVs into the raw archive and raw tables.
3. Rebuilds staging tables.
4. Runs reconciliation validation.
5. Writes Loguru logs to `LOG_DIR`.
6. Sends a failure email if any step fails.

The default source is `PIPELINE_FETCH_SOURCE=flex`, which calls IBKR Flex Web Service. Use `PIPELINE_FETCH_SOURCE=local` to skip remote fetching and process files already present in `data/inbox`.
Scheduled launchd runs pass `--notify-success`, so they send a minimal success email after data loads and validation passes. Manual/dev runs stay quiet unless you pass `--notify-success` yourself.

Dry-run the Flex Web Service request path:

```bash
/Users/mbailey/opt/anaconda3/envs/py311/bin/python scripts/fetch_flex_statement.py --dry-run
```

## macOS Schedule

Install the daily `launchd` job:

```bash
make PYTHON=/Users/mbailey/opt/anaconda3/envs/py311/bin/python install-schedule
```

Remove it:

```bash
make PYTHON=/Users/mbailey/opt/anaconda3/envs/py311/bin/python uninstall-schedule
```

The schedule uses:

```text
PIPELINE_SCHEDULE_HOUR=20
PIPELINE_SCHEDULE_MINUTE=0
```

## Environment

Required for Flex Web Service fetching:

```text
PIPELINE_FETCH_SOURCE=flex
IBKR_FLEX_TOKEN=your_flex_web_service_token
IBKR_FLEX_QUERY_ID=your_flex_query_id
IBKR_FLEX_BASE_URL=https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService
IBKR_FLEX_API_VERSION=3
IBKR_FLEX_POLL_SECONDS=5
IBKR_FLEX_MAX_POLLS=12
IBKR_FLEX_OUTPUT_NAME=ibkr_flex_statement.csv
```

The Flex query should return a sectioned CSV with `BOF`, `BOA`, `BOS`, `HEADER`, `DATA`, `EOS`, `EOA`, and `EOF` rows. The MVP parser currently stages `EQUT`, `CNAV`, `POST`, `TRNT`, `CTRN`, `CORP`, and `TIER`.

Optional notification overrides:

```text
SMTP_HOST=smtp.mail.me.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=your_icloud_email@example.com
SMTP_PASSWORD=your_app_specific_password
NOTIFY_EMAIL_FROM=your_icloud_email@example.com
NOTIFY_EMAIL_TO=your_notification_email@example.com
```

If SMTP values are omitted, the pipeline also accepts the legacy `EMAIL_USER` and `EMAIL_APP_PASSWORD` environment variables as SMTP fallbacks.

## Logs

- `logs/pipeline.log`: scheduled pipeline
- `logs/launchd.out.log`: launchd stdout
- `logs/launchd.err.log`: launchd stderr
- `logs/fetch_flex.log`: manual Flex Web Service fetch
- `logs/ingest_local.log`: manual local ingestion
- `logs/transforms.log`: manual staging rebuild
- `logs/validation.log`: manual reconciliation validation

## Full-History Reports

YTD or full-history reports are acceptable.

The raw layer dedupes exact files by SHA-256 and retains changed restatements as new immutable source files. The staging layer rebuilds from raw rows and upserts by business keys, so later ingested history wins while preserving the raw audit trail.
