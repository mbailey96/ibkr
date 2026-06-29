from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from psycopg.types.json import Jsonb

from portfolio_warehouse.db import connect
from portfolio_warehouse.ibkr_csv import (
    detect_report_type,
    file_sha256,
    iter_flex_section_rows,
    iter_flex_rows,
    iter_portfolio_summary_rows,
    safe_filename,
)
from portfolio_warehouse.settings import get_settings


@dataclass(frozen=True)
class IngestResult:
    path: Path
    report_type: str
    report_id: uuid.UUID | None
    row_count: int
    skipped: bool


def csv_files_from_paths(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.csv")))
        elif path.suffix.lower() == ".csv":
            files.append(path)
    return files


def _archive_path(raw_root: Path, report_type: str, digest: str, source_path: Path) -> Path:
    today = date.today()
    return (
        raw_root
        / "ibkr"
        / report_type
        / f"year={today:%Y}"
        / f"month={today:%m}"
        / f"{digest[:16]}_{safe_filename(source_path.name)}"
    )


def ingest_file(path: str | Path) -> IngestResult:
    settings = get_settings()
    source_path = Path(path)
    report_type = detect_report_type(source_path)
    digest = file_sha256(source_path)

    with connect() as conn:
        existing = conn.execute(
            "select report_id, row_count from raw.report_file where file_sha256 = %s",
            (digest,),
        ).fetchone()
        if existing:
            return IngestResult(source_path, report_type, existing["report_id"], existing["row_count"] or 0, True)

        report_id = uuid.uuid4()
        archive_path = _archive_path(settings.raw_data_dir, report_type, digest, source_path)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, archive_path)

        if report_type == "portfolio_summary":
            rows = list(iter_portfolio_summary_rows(source_path))
        elif report_type == "flex_statement":
            rows = list(iter_flex_section_rows(source_path))
        else:
            rows = list(iter_flex_rows(source_path))

        with conn.transaction():
            conn.execute(
                """
                insert into raw.report_file (
                    report_id, source_system, report_type, original_filename,
                    stored_file_path, file_sha256, parser_version, row_count, metadata
                )
                values (%s, 'ibkr', %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_id,
                    report_type,
                    source_path.name,
                    str(archive_path),
                    digest,
                    "mvp-0.1",
                    len(rows),
                    Jsonb({"source_path": str(source_path)}),
                ),
            )

            if report_type == "portfolio_summary":
                for row in rows:
                    conn.execute(
                        """
                        insert into raw.ibkr_portfolio_summary_row (
                            report_id, row_number, section, row_type, raw_values
                        )
                        values (%s, %s, %s, %s, %s)
                        """,
                        (report_id, row.row_number, row.section, row.row_type, Jsonb(row.raw_values)),
                    )
            elif report_type == "flex_statement":
                for row in rows:
                    conn.execute(
                        """
                        insert into raw.ibkr_flex_statement_row (
                            report_id, row_number, account_id, section_code, section_name, raw_payload
                        )
                        values (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            report_id,
                            row.row_number,
                            row.account_id,
                            row.section_code,
                            row.section_name,
                            Jsonb(row.payload),
                        ),
                    )
            else:
                for row in rows:
                    conn.execute(
                        """
                        insert into raw.ibkr_flex_row (
                            report_id, report_type, row_number, raw_payload
                        )
                        values (%s, %s, %s, %s)
                        """,
                        (report_id, report_type, row.row_number, Jsonb(row.payload)),
                    )

        return IngestResult(source_path, report_type, report_id, len(rows), False)


def ingest_paths(paths: Iterable[str | Path]) -> list[IngestResult]:
    return [ingest_file(path) for path in csv_files_from_paths(paths)]
