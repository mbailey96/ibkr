from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.settings import get_settings
from portfolio_warehouse.transforms import rebuild_staging


def main() -> int:
    settings = get_settings()
    configure_logging(log_dir=settings.log_dir, log_name="transforms.log", level=settings.log_level)
    rebuild_staging()
    logger.info("Rebuilt staging tables from raw rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
