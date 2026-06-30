from __future__ import annotations

import socket
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from portfolio_warehouse.db import connect
from portfolio_warehouse.flex_web import fetch_flex_statement
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
    downloaded_files: int = 0
    ingest_results: list[IngestResult] = field(default_factory=list)
    validation_messages: list[str] = field(default_factory=list)

    @property
    def ingested_count(self) -> int:
        return sum(1 for result in self.ingest_results if not result.skipped)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.ingest_results if result.skipped)


def run_pipeline(*, settings: Settings | None = None, dry_run_fetch: bool = False) -> PipelineResult:
    settings = settings or get_settings()
    result = PipelineResult(started_at=datetime.now())

    logger.info("Starting IBKR portfolio warehouse pipeline")
    if settings.pipeline_fetch_source == "flex":
        flex_result = _timed_step("fetch_flex", lambda: fetch_flex_statement(settings=settings, dry_run=dry_run_fetch))
        if flex_result is not None:
            result.downloaded_files = 1
            logger.info(
                "Downloaded Flex statement to {} ({} bytes, reference={})",
                flex_result.stored_path,
                flex_result.byte_count,
                flex_result.reference_code,
            )
    elif settings.pipeline_fetch_source in {"none", "local"}:
        logger.info("Skipping remote fetch because PIPELINE_FETCH_SOURCE={}", settings.pipeline_fetch_source)
    else:
        raise ValueError("PIPELINE_FETCH_SOURCE must be one of: flex, local, none")

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
    _record_successful_run(result)
    logger.info(
        "Pipeline complete: ingested={}, skipped={}, validation_messages={}",
        result.ingested_count,
        result.skipped_count,
        len(result.validation_messages),
    )
    return result


def _record_successful_run(result: PipelineResult) -> None:
    finished_at = result.finished_at or datetime.now()
    with connect() as conn:
        conn.execute(
            """
            insert into raw.pipeline_run (
                run_id, source_system, status, started_at, finished_at, downloaded_files,
                ingested_files, skipped_files, validation_message_count
            )
            values (%s, 'ibkr', 'success', %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid.uuid4(),
                result.started_at,
                finished_at,
                result.downloaded_files,
                result.ingested_count,
                result.skipped_count,
                len(result.validation_messages),
            ),
        )
        conn.commit()


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
    subject = "IBKR portfolio warehouse loaded successfully"
    finished = result.finished_at or datetime.now()
    body = "\n".join(
        [
            "IBKR portfolio warehouse data loaded successfully.",
            "",
            f"Started: {result.started_at.isoformat(timespec='seconds')}",
            f"Finished: {finished.isoformat(timespec='seconds')}",
            f"Flex files downloaded: {result.downloaded_files}",
            f"Files ingested: {result.ingested_count}",
            f"Files skipped: {result.skipped_count}",
            f"Validation messages: {len(result.validation_messages)}",
            f"Log file: {log_path}",
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
