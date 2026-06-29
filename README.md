# IBKR Portfolio Warehouse

Local portfolio warehouse for IBKR reports, backed by Postgres and a Dash dashboard.

## What It Does

```text
IBKR Flex Web Service or local CSV files
  -> data/inbox
  -> immutable raw archive and raw Postgres tables
  -> typed staging tables
  -> analytics views
  -> Dash dashboard
```

Supported inputs:

- Sectioned Flex statement CSVs, including NAV, positions, trades, cash, corporate actions, and interest tiers
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
make ingest-local
make rebuild-staging
make validate
make app
```

Dash runs at http://localhost:8050.

## Daily Pipeline

```bash
make run-pipeline
```

The pipeline fetches the configured IBKR source, ingests new local files, rebuilds staging, validates reconciliation, writes Loguru logs under `logs/`, and sends an email on failure.
By default, `PIPELINE_FETCH_SOURCE=flex` downloads the configured Flex query via IBKR Flex Web Service. Use `PIPELINE_FETCH_SOURCE=local` to skip remote fetching and only ingest files already present in `data/inbox`.
Scheduled runs also send a minimal success email after data loads and validation passes. Manual/dev runs do not send success emails unless run with `--notify-success`.

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
make fetch-flex
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
- downloaded or manually staged source files under `data/inbox/`
- logs under `logs/`
- Python caches and virtual environments

Only `.gitkeep` placeholders are tracked in data/log directories.

## Docs

- [Operations](docs/db_access_and_scheduling.md)
- [IBKR report setup](docs/ibkr_report_setup.md)
