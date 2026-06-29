from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.pipeline import notify_failure, notify_success, run_pipeline
from portfolio_warehouse.settings import get_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the scheduled IBKR portfolio warehouse pipeline.")
    parser.add_argument("--dry-run-email", action="store_true", help="Scan matching emails without saving attachments or moving messages.")
    parser.add_argument("--no-failure-email", action="store_true", help="Do not send a failure notification email.")
    parser.add_argument("--notify-success", action="store_true", help="Send a success notification email for this run.")
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    settings = get_settings()
    log_path = configure_logging(log_dir=settings.log_dir, log_name="pipeline.log", level=settings.log_level)

    try:
        result = run_pipeline(settings=settings, dry_run_email=args.dry_run_email)
    except Exception as exc:
        logger.exception("Pipeline failed")
        if not args.no_failure_email:
            try:
                notify_failure(settings=settings, log_path=str(log_path), exc=exc)
            except Exception:
                logger.exception("Failure notification email could not be sent")
        return 1

    if args.notify_success or settings.notify_on_success:
        try:
            notify_success(settings=settings, result=result, log_path=str(log_path))
        except Exception:
            logger.exception("Success notification email could not be sent")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
