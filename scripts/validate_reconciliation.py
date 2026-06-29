from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.settings import get_settings
from portfolio_warehouse.validation import run_validation


def main() -> int:
    settings = get_settings()
    configure_logging(log_dir=settings.log_dir, log_name="validation.log", level=settings.log_level)
    warning_found = False
    for message in run_validation():
        if message.startswith("WARNING:"):
            logger.warning(message)
            warning_found = True
        else:
            logger.info(message)
    if warning_found:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
