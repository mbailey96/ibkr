from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger

from portfolio_warehouse.email_fetch import EmailFetchError, fetch_ibkr_attachments
from portfolio_warehouse.logging import configure_logging
from portfolio_warehouse.settings import get_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download expected IBKR CSV attachments from iCloud IMAP.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report matching attachments without writing files or moving messages.")
    parser.add_argument("--no-move", action="store_true", help="Do not move processed messages after saving attachments.")
    parser.add_argument("--limit", type=int, help="Only inspect the newest N messages returned by the IMAP search.")
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    settings = get_settings()
    configure_logging(log_dir=settings.log_dir, log_name="fetch_email.log", level=settings.log_level)
    try:
        result = fetch_ibkr_attachments(
            settings=settings,
            dry_run=args.dry_run,
            move_processed=not args.no_move,
            limit=args.limit,
        )
    except EmailFetchError as exc:
        logger.error("Email fetch failed: {}", exc)
        return 1

    logger.info(
        "Email fetch complete: "
        "scanned={}, matched={}, attachments={}, moved={}",
        result.scanned_messages,
        result.matched_messages,
        len(result.attachments),
        result.moved_messages,
    )
    for attachment in result.attachments:
        logger.info(
            "{}: {} -> {} ({} bytes)",
            attachment.report_type,
            attachment.original_filename,
            attachment.stored_path,
            attachment.byte_count,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
