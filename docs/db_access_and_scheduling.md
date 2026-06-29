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

1. Fetches matching IBKR CSV/ZIP attachments from iCloud IMAP into `data/inbox`.
2. Moves processed messages to `EMAIL_PROCESSED_FOLDER`.
3. Ingests inbox CSVs into the raw archive and raw tables.
4. Rebuilds staging tables.
5. Runs reconciliation validation.
6. Writes Loguru logs to `LOG_DIR`.
7. Sends a failure email if any step fails.

Dry-run the email fetch path:

```bash
/Users/mbailey/opt/anaconda3/envs/py311/bin/python scripts/run_pipeline.py --dry-run-email --no-failure-email
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
PIPELINE_SCHEDULE_HOUR=8
PIPELINE_SCHEDULE_MINUTE=15
```

## Environment

Required for email fetching:

```text
EMAIL_USER=your_icloud_email@example.com
EMAIL_APP_PASSWORD=your_app_specific_password
EMAIL_FOLDER=INBOX
EMAIL_PROCESSED_FOLDER=IBKR Processed
```

Optional notification overrides:

```text
SMTP_HOST=smtp.mail.me.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=your_icloud_email@example.com
SMTP_PASSWORD=your_app_specific_password
NOTIFY_EMAIL_FROM=your_icloud_email@example.com
NOTIFY_EMAIL_TO=your_notification_email@example.com
NOTIFY_ON_SUCCESS=false
```

If SMTP values are omitted, the pipeline reuses `EMAIL_USER` and `EMAIL_APP_PASSWORD`. If `NOTIFY_EMAIL_TO` is omitted, it falls back to `EMAIL_USER`.

## Logs

- `logs/pipeline.log`: scheduled pipeline
- `logs/launchd.out.log`: launchd stdout
- `logs/launchd.err.log`: launchd stderr
- `logs/fetch_email.log`: manual email fetch
- `logs/ingest_local.log`: manual local ingestion
- `logs/transforms.log`: manual staging rebuild
- `logs/validation.log`: manual reconciliation validation

## Full-History Reports

YTD or full-history reports are acceptable.

The raw layer dedupes exact files by SHA-256 and retains changed restatements as new immutable source files. The staging layer rebuilds from raw rows and upserts by business keys, so later ingested history wins while preserving the raw audit trail.
