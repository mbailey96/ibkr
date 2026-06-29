-include .env
export

DATABASE_URL ?= postgresql://portfolio:portfolio_dev_password@localhost:55432/portfolio
RAW_DATA_DIR ?= ./data/raw
INBOX_DIR ?= ./data/inbox
SAMPLE_DIR ?= ../temp_files
PYTHON ?= python

.PHONY: init-db fetch-flex ingest-local ingest-samples rebuild-staging validate run-pipeline install-schedule uninstall-schedule app test

init-db:
	$(PYTHON) scripts/initialise_db.py

fetch-flex:
	$(PYTHON) scripts/fetch_flex_statement.py

ingest-local:
	$(PYTHON) scripts/ingest_local_files.py data/inbox

ingest-samples:
	$(PYTHON) scripts/ingest_local_files.py "$${SAMPLE_DIR}"

rebuild-staging:
	$(PYTHON) scripts/run_transforms.py

validate:
	$(PYTHON) scripts/validate_reconciliation.py

run-pipeline:
	$(PYTHON) scripts/run_pipeline.py

install-schedule:
	$(PYTHON) scripts/install_launchd_schedule.py

uninstall-schedule:
	$(PYTHON) scripts/install_launchd_schedule.py --uninstall

app:
	PYTHONPATH=src $(PYTHON) app/dash_app.py

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests
