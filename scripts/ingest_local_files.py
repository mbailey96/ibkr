from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.ingest_files import ingest_paths
from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.settings import get_settings


def main(argv: list[str]) -> int:
    settings = get_settings()
    configure_logging(log_dir=settings.log_dir, log_name="ingest_local.log", level=settings.log_level)
    paths = argv[1:] or ["data/inbox"]
    results = ingest_paths(paths)
    if not results:
        logger.info("No CSV files found.")
        return 0
    for result in results:
        status = "skipped" if result.skipped else "ingested"
        logger.info(
            "{}: {} ({}, rows={}, report_id={})",
            status,
            result.path,
            result.report_type,
            result.row_count,
            result.report_id,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
