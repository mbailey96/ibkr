# IBKR Portfolio Warehouse

Local portfolio warehouse for IBKR reports, backed by Postgres and a Dash dashboard.

## What It Does

```text
IBKR CSV/ZIP email attachments
  -> data/inbox
  -> immutable raw archive and raw Postgres tables
  -> typed staging tables
  -> analytics views
  -> Dash dashboard
```

Supported inputs:

- PortfolioAnalyst summary CSVs
- Flex `Trades.csv`
- Flex `Cash.csv`
- Flex `Interest.csv`
- Flex `Corporate_Actions.csv`

## Quick Start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres
make init-db
make ingest-samples SAMPLE_DIR=../temp_files
make rebuild-staging
make validate
make app
```

Dash runs at http://localhost:8050.

## Daily Pipeline

```bash
make run-pipeline
```

The pipeline fetches matching iCloud IMAP attachments, ingests new local files, rebuilds staging, validates reconciliation, writes Loguru logs under `logs/`, and sends an email on failure.

Install the local macOS schedule:

```bash
make install-schedule
```

Remove it:

```bash
make uninstall-schedule
```

## Common Commands

```bash
make init-db
make fetch-email
make ingest-local
make rebuild-staging
make validate
make run-pipeline
make app
make test
```

## Data Safety

The repo intentionally excludes:

- `.env`
- raw IBKR files under `data/raw/`
- downloaded email attachments under `data/inbox/`
- logs under `logs/`
- Python caches and virtual environments

Only `.gitkeep` placeholders are tracked in data/log directories.

## Docs

- [Operations](docs/db_access_and_scheduling.md)
- [IBKR report setup](docs/ibkr_report_setup.md)
