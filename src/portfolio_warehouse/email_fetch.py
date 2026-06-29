from __future__ import annotations

import email
import imaplib
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

from loguru import logger

from portfolio_warehouse.ibkr_csv import detect_report_type, safe_filename
from portfolio_warehouse.settings import Settings, get_settings


@dataclass(frozen=True)
class DownloadedAttachment:
    message_uid: str
    original_filename: str
    report_type: str
    stored_path: Path
    byte_count: int


@dataclass(frozen=True)
class EmailFetchResult:
    scanned_messages: int
    matched_messages: int
    moved_messages: int
    attachments: list[DownloadedAttachment]


class EmailFetchError(RuntimeError):
    pass


def fetch_ibkr_attachments(
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
    move_processed: bool = True,
    limit: int | None = None,
) -> EmailFetchResult:
    settings = settings or get_settings()
    if not settings.email_user or not settings.email_app_password:
        raise EmailFetchError("EMAIL_USER and EMAIL_APP_PASSWORD must be set before fetching email.")

    attachments: list[DownloadedAttachment] = []
    scanned = 0
    matched = 0
    moved = 0

    try:
        with imaplib.IMAP4_SSL(settings.email_host, settings.email_port) as client:
            logger.info("Connecting to IMAP host {}:{}", settings.email_host, settings.email_port)
            _check(client.login(settings.email_user, settings.email_app_password), "login")
            logger.info("Authenticated to IMAP as {}", settings.email_user)
            if move_processed and not dry_run:
                _ensure_mailbox(client, settings.email_processed_folder)
            _check(client.select(_quote_mailbox(settings.email_folder)), f"select {settings.email_folder}")
            message_uids = _search_uids(client, settings.email_lookback_days)
            if limit is not None:
                message_uids = message_uids[-limit:]
            logger.info("IMAP search returned {} message(s)", len(message_uids))

            for uid in message_uids:
                scanned += 1
                raw_message = _fetch_message(client, uid)
                message = email.message_from_bytes(raw_message)
                if not _matches_ibkr_message(message, settings):
                    logger.debug("Skipping non-matching email UID {}", uid)
                    continue
                matched += 1
                logger.info("Matched IBKR email UID {} with subject {!r}", uid, _decode_header(message.get("Subject")))

                saved = _save_expected_attachments(
                    message,
                    uid=uid,
                    inbox_dir=settings.inbox_dir,
                    dry_run=dry_run,
                )
                attachments.extend(saved)
                if saved and move_processed and not dry_run:
                    _move_message(client, uid, settings.email_processed_folder)
                    moved += 1
                    logger.info("Moved processed email UID {} to {}", uid, settings.email_processed_folder)

            if moved:
                client.expunge()
            client.logout()
    except imaplib.IMAP4.error as exc:
        raise EmailFetchError(f"IMAP error: {_decode_imap_error(exc)}") from exc
    except OSError as exc:
        raise EmailFetchError(f"Network error connecting to {settings.email_host}:{settings.email_port}: {exc}") from exc

    return EmailFetchResult(
        scanned_messages=scanned,
        matched_messages=matched,
        moved_messages=moved,
        attachments=attachments,
    )


def _check(response: tuple[str, list[bytes] | list[tuple[bytes, bytes]]], action: str) -> None:
    status = response[0]
    if status != "OK":
        raise EmailFetchError(f"IMAP {action} failed: {response}")


def _decode_imap_error(exc: imaplib.IMAP4.error) -> str:
    if not exc.args:
        return str(exc)
    value = exc.args[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _quote_mailbox(mailbox: str) -> str:
    escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _ensure_mailbox(client: imaplib.IMAP4_SSL, mailbox: str) -> None:
    status, _ = client.create(_quote_mailbox(mailbox))
    if status not in {"OK", "NO"}:
        raise EmailFetchError(f"Could not create or verify mailbox {mailbox!r}")


def _search_uids(client: imaplib.IMAP4_SSL, lookback_days: int) -> list[str]:
    since = date.today() - timedelta(days=lookback_days)
    since_value = since.strftime("%d-%b-%Y")
    status, data = client.uid("search", None, "SINCE", since_value)
    if status != "OK":
        raise EmailFetchError(f"IMAP search failed: {data}")
    if not data or not data[0]:
        return []
    return data[0].decode("ascii").split()


def _fetch_message(client: imaplib.IMAP4_SSL, uid: str) -> bytes:
    status, data = client.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK":
        raise EmailFetchError(f"IMAP fetch failed for UID {uid}: {data}")
    for item in data:
        if isinstance(item, tuple):
            return item[1]
    raise EmailFetchError(f"No message payload returned for UID {uid}")


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _matches_ibkr_message(message: Message, settings: Settings) -> bool:
    from_header = _decode_header(message.get("From"))
    subject = _decode_header(message.get("Subject")).lower()
    addresses = " ".join(address for _, address in getaddresses([from_header])).lower()
    from_text = f"{from_header} {addresses}".lower()
    from_match = settings.ibkr_email_from_contains.lower() in from_text
    subject_match = not settings.ibkr_email_subject_contains or any(
        pattern in subject for pattern in settings.ibkr_email_subject_contains
    )
    return from_match and subject_match


def _save_expected_attachments(
    message: Message,
    *,
    uid: str,
    inbox_dir: Path,
    dry_run: bool,
) -> list[DownloadedAttachment]:
    saved: list[DownloadedAttachment] = []
    message_date = _message_date_prefix(message)
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = _decode_header(part.get_filename())
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        for extracted_name, content in _iter_attachment_files(filename, payload):
            report_type = _detect_expected_report_type(extracted_name)
            if not report_type:
                continue
            stored_path = _target_path(
                inbox_dir=inbox_dir,
                report_type=report_type,
                message_date=message_date,
                uid=uid,
                filename=extracted_name,
            )
            if not dry_run:
                stored_path.parent.mkdir(parents=True, exist_ok=True)
                if not stored_path.exists():
                    stored_path.write_bytes(content)
                    logger.info("Saved attachment {} to {}", extracted_name, stored_path)
                else:
                    logger.info("Attachment already exists at {}", stored_path)
            else:
                logger.info("Dry-run matched attachment {} for {}", extracted_name, stored_path)
            saved.append(
                DownloadedAttachment(
                    message_uid=uid,
                    original_filename=extracted_name,
                    report_type=report_type,
                    stored_path=stored_path,
                    byte_count=len(content),
                )
            )
    return saved


def _iter_attachment_files(filename: str, payload: bytes) -> Iterable[tuple[str, bytes]]:
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.lower().endswith(".csv"):
                    continue
                yield Path(member.filename).name, archive.read(member)
        return
    if filename.lower().endswith(".csv"):
        yield filename, payload


def _detect_expected_report_type(filename: str) -> str | None:
    try:
        return detect_report_type(filename)
    except ValueError:
        return None


def _message_date_prefix(message: Message) -> str:
    raw_date = message.get("Date")
    if raw_date:
        try:
            return parsedate_to_datetime(raw_date).date().strftime("%Y%m%d")
        except (TypeError, ValueError):
            pass
    return date.today().strftime("%Y%m%d")


def _target_path(
    *,
    inbox_dir: Path,
    report_type: str,
    message_date: str,
    uid: str,
    filename: str,
) -> Path:
    clean_name = safe_filename(filename)
    return inbox_dir / "ibkr" / report_type / f"{message_date}_uid{uid}_{clean_name}"


def _move_message(client: imaplib.IMAP4_SSL, uid: str, mailbox: str) -> None:
    status, data = client.uid("MOVE", uid, _quote_mailbox(mailbox))
    if status == "OK":
        return
    copy_status, copy_data = client.uid("COPY", uid, _quote_mailbox(mailbox))
    if copy_status != "OK":
        raise EmailFetchError(f"Could not move UID {uid} to {mailbox!r}: {data}; COPY failed: {copy_data}")
    store_status, store_data = client.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
    if store_status != "OK":
        raise EmailFetchError(f"Copied UID {uid} but could not mark original deleted: {store_data}")
