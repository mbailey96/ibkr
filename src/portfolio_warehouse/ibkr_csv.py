from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator


REPORT_PATTERNS: dict[str, tuple[str, ...]] = {
    "flex_trades": ("trades",),
    "flex_cash": ("cash",),
    "flex_interest": ("interest",),
    "flex_corporate_actions": ("corporate_actions", "corporate actions"),
    "portfolio_summary": ("inception", "portfolio"),
}


@dataclass(frozen=True)
class ParsedRow:
    row_number: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class ParsedPortfolioRow:
    row_number: int
    section: str
    row_type: str
    raw_values: dict[str, Any]


@dataclass(frozen=True)
class ParsedFlexSectionRow:
    row_number: int
    account_id: str | None
    section_code: str
    section_name: str | None
    payload: dict[str, Any]


def detect_report_type(path: str | Path) -> str:
    if Path(path).exists() and is_sectioned_flex_file(path):
        return "flex_statement"
    name = Path(path).name.lower()
    for report_type, patterns in REPORT_PATTERNS.items():
        if any(pattern in name for pattern in patterns):
            return report_type
    raise ValueError(f"Could not detect IBKR report type for {Path(path).name}")


def is_sectioned_flex_file(path: str | Path) -> bool:
    with Path(path).open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            return row[0].strip() == "BOF"
    return False


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def iter_flex_rows(path: str | Path) -> Iterator[ParsedRow]:
    header: list[str] | None = None
    with Path(path).open(newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if header is None:
                header = row
                continue
            if row[: len(header)] == header:
                continue
            payload = {column: row[index] if index < len(row) else "" for index, column in enumerate(header)}
            if len(row) > len(header):
                payload["_extra_columns"] = row[len(header) :]
            yield ParsedRow(row_number=row_number, payload=payload)


def iter_portfolio_summary_rows(path: str | Path) -> Iterator[ParsedPortfolioRow]:
    with Path(path).open(newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if len(row) < 2 or not any(cell.strip() for cell in row):
                continue
            yield ParsedPortfolioRow(
                row_number=row_number,
                section=row[0].strip(),
                row_type=row[1].strip(),
                raw_values={"values": row[2:]},
            )


def iter_flex_section_rows(path: str | Path) -> Iterator[ParsedFlexSectionRow]:
    account_id: str | None = None
    section_code: str | None = None
    section_name: str | None = None
    header: list[str] | None = None
    section_row_number = 0

    with Path(path).open(newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            marker = row[0].strip()
            if marker == "BOA":
                account_id = row[1].strip() if len(row) > 1 and row[1].strip() else None
                continue
            if marker == "EOA":
                account_id = None
                continue
            if marker == "BOS":
                section_code = row[1].strip() if len(row) > 1 else None
                section_name = row[2].strip() if len(row) > 2 and row[2].strip() else None
                header = None
                section_row_number = 0
                continue
            if marker == "HEADER":
                if len(row) > 1:
                    section_code = row[1].strip()
                header = row[2:]
                section_row_number = 0
                continue
            if marker == "EOS":
                section_code = None
                section_name = None
                header = None
                section_row_number = 0
                continue
            if marker != "DATA" or not section_code or header is None:
                continue

            row_section_code = row[1].strip() if len(row) > 1 else section_code
            values = row[2:]
            payload = {column: values[index] if index < len(values) else "" for index, column in enumerate(header)}
            if len(values) > len(header):
                payload["_extra_columns"] = values[len(header) :]
            section_row_number += 1
            payload["_section_row_number"] = section_row_number
            yield ParsedFlexSectionRow(
                row_number=row_number,
                account_id=account_id,
                section_code=row_section_code,
                section_name=section_name,
                payload=payload,
            )


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", " "}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    for fmt in ("%Y-%m-%d;%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_period(value: str) -> tuple[date | None, date | None]:
    text = value.strip()
    separators = (" - ", " to ")
    for separator in separators:
        if separator in text:
            left, right = text.split(separator, 1)
            return parse_date(left), parse_date(right)
    return None, None
