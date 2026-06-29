from __future__ import annotations

import socket
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from portfolio_warehouse.email_fetch import fetch_ibkr_attachments
from portfolio_warehouse.ingest_files import IngestResult, ingest_paths
from portfolio_warehouse.notifications import send_notification_email
from portfolio_warehouse.settings import Settings, get_settings
from portfolio_warehouse.transforms import rebuild_staging
from portfolio_warehouse.validation import run_validation


class PipelineValidationError(RuntimeError):
    pass


@dataclass
class PipelineResult:
    started_at: datetime
    finished_at: datetime | None = None
    scanned_messages: int = 0
    matched_messages: int = 0
    downloaded_attachments: int = 0
    moved_messages: int = 0
    ingest_results: list[IngestResult] = field(default_factory=list)
    validation_messages: list[str] = field(default_factory=list)

    @property
    def ingested_count(self) -> int:
        return sum(1 for result in self.ingest_results if not result.skipped)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.ingest_results if result.skipped)


def run_pipeline(*, settings: Settings | None = None, dry_run_email: bool = False) -> PipelineResult:
    settings = settings or get_settings()
    result = PipelineResult(started_at=datetime.now())

    logger.info("Starting IBKR portfolio warehouse pipeline")
    email_result = _timed_step(
        "fetch_email",
        lambda: fetch_ibkr_attachments(
            settings=settings,
            dry_run=dry_run_email,
            move_processed=not dry_run_email,
            limit=settings.pipeline_email_limit,
        ),
    )
    result.scanned_messages = email_result.scanned_messages
    result.matched_messages = email_result.matched_messages
    result.downloaded_attachments = len(email_result.attachments)
    result.moved_messages = email_result.moved_messages
    logger.info(
        "Email fetch complete: scanned={}, matched={}, attachments={}, moved={}",
        result.scanned_messages,
        result.matched_messages,
        result.downloaded_attachments,
        result.moved_messages,
    )
    for attachment in email_result.attachments:
        logger.info(
            "Downloaded {} attachment {} to {} ({} bytes)",
            attachment.report_type,
            attachment.original_filename,
            attachment.stored_path,
            attachment.byte_count,
        )

    result.ingest_results = _timed_step("ingest_local_files", lambda: ingest_paths([settings.inbox_dir]))
    if not result.ingest_results:
        logger.info("No local CSV files found in {}", settings.inbox_dir)
    for ingest_result in result.ingest_results:
        logger.info(
            "{} {} ({}, rows={}, report_id={})",
            "Skipped duplicate" if ingest_result.skipped else "Ingested",
            ingest_result.path,
            ingest_result.report_type,
            ingest_result.row_count,
            ingest_result.report_id,
        )

    _timed_step("rebuild_staging", rebuild_staging)
    logger.info("Rebuilt staging tables from raw rows")

    result.validation_messages = _timed_step("validate_reconciliation", run_validation)
    for message in result.validation_messages:
        if message.startswith("WARNING:"):
            logger.warning(message)
        else:
            logger.info(message)
    warnings = [message for message in result.validation_messages if message.startswith("WARNING:")]
    if warnings:
        raise PipelineValidationError("; ".join(warnings))

    result.finished_at = datetime.now()
    logger.info(
        "Pipeline complete: ingested={}, skipped={}, validation_messages={}",
        result.ingested_count,
        result.skipped_count,
        len(result.validation_messages),
    )
    return result


def notify_failure(*, settings: Settings, log_path: str, exc: BaseException) -> bool:
    subject = "IBKR portfolio warehouse pipeline failed"
    body = "\n".join(
        [
            "The scheduled IBKR portfolio warehouse pipeline failed.",
            "",
            f"Host: {socket.gethostname()}",
            f"Time: {datetime.now().isoformat(timespec='seconds')}",
            f"Log file: {log_path}",
            "",
            "Error:",
            "".join(traceback.format_exception_only(type(exc), exc)).strip(),
            "",
            "Traceback:",
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        ]
    )
    return send_notification_email(settings=settings, subject=subject, body=body)


def notify_success(*, settings: Settings, result: PipelineResult, log_path: str) -> bool:
    subject = "IBKR portfolio warehouse pipeline succeeded"
    finished = result.finished_at or datetime.now()
    body = "\n".join(
        [
            "The scheduled IBKR portfolio warehouse pipeline completed successfully.",
            "",
            f"Host: {socket.gethostname()}",
            f"Started: {result.started_at.isoformat(timespec='seconds')}",
            f"Finished: {finished.isoformat(timespec='seconds')}",
            f"Log file: {log_path}",
            "",
            f"Emails scanned: {result.scanned_messages}",
            f"Emails matched: {result.matched_messages}",
            f"Attachments downloaded: {result.downloaded_attachments}",
            f"Messages moved: {result.moved_messages}",
            f"Files ingested: {result.ingested_count}",
            f"Files skipped: {result.skipped_count}",
        ]
    )
    return send_notification_email(settings=settings, subject=subject, body=body)


def _timed_step(name: str, func):
    started = time.monotonic()
    logger.info("Step started: {}", name)
    try:
        value = func()
    except Exception:
        logger.exception("Step failed: {}", name)
        raise
    elapsed = time.monotonic() - started
    logger.info("Step complete: {} ({:.2f}s)", name, elapsed)
    return value
