from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.flex_web import FlexWebError, fetch_flex_statement
from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.settings import get_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a sectioned IBKR Flex statement via Flex Web Service.")
    parser.add_argument("--dry-run", action="store_true", help="Send the request but do not poll or save the statement.")
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    settings = get_settings()
    configure_logging(log_dir=settings.log_dir, log_name="fetch_flex.log", level=settings.log_level)
    try:
        result = fetch_flex_statement(settings=settings, dry_run=args.dry_run)
    except FlexWebError as exc:
        logger.error("Flex fetch failed: {}", exc)
        return 1

    if result is None:
        logger.info("Flex dry run completed successfully.")
    else:
        logger.info("Downloaded Flex statement {} bytes to {}", result.byte_count, result.stored_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
