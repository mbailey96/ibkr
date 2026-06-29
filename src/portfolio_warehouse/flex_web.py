from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from loguru import logger

from portfolio_warehouse.ibkr_csv import safe_filename
from portfolio_warehouse.settings import Settings, get_settings


class FlexWebError(RuntimeError):
    pass


@dataclass(frozen=True)
class FlexFetchResult:
    reference_code: str
    stored_path: Path
    byte_count: int


def fetch_flex_statement(*, settings: Settings | None = None, dry_run: bool = False) -> FlexFetchResult | None:
    settings = settings or get_settings()
    if not settings.ibkr_flex_token:
        raise FlexWebError("IBKR_FLEX_TOKEN is not configured")
    if not settings.ibkr_flex_query_id:
        raise FlexWebError("IBKR_FLEX_QUERY_ID is not configured")

    reference_code = _send_request(settings)
    logger.info("Flex request accepted with reference code {}", reference_code)
    if dry_run:
        return None

    content = _poll_statement(settings, reference_code)
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    output_name = _statement_filename(settings.ibkr_flex_output_name)
    output_path = settings.inbox_dir / output_name
    output_path.write_bytes(content)
    return FlexFetchResult(reference_code=reference_code, stored_path=output_path, byte_count=len(content))


def _send_request(settings: Settings) -> str:
    url = _build_url(
        settings,
        "SendRequest",
        {"t": settings.ibkr_flex_token, "q": settings.ibkr_flex_query_id, "v": str(settings.ibkr_flex_api_version)},
    )
    content = _http_get(url)
    root = _parse_xml(content, "Flex SendRequest")
    status = _xml_text(root, "Status")
    if status and status.lower() != "success":
        raise FlexWebError(_xml_error(root, "Flex SendRequest failed"))
    reference_code = _xml_text(root, "ReferenceCode")
    if not reference_code:
        raise FlexWebError(f"Flex SendRequest response did not include a ReferenceCode: {content[:300]!r}")
    return reference_code


def _poll_statement(settings: Settings, reference_code: str) -> bytes:
    url = _build_url(
        settings,
        "GetStatement",
        {"t": settings.ibkr_flex_token, "q": reference_code, "v": str(settings.ibkr_flex_api_version)},
    )
    last_error: str | None = None
    for attempt in range(1, settings.ibkr_flex_max_polls + 1):
        content = _http_get(url)
        if _looks_like_statement(content):
            logger.info("Flex statement ready on poll attempt {}", attempt)
            return content

        try:
            root = _parse_xml(content, "Flex GetStatement")
        except FlexWebError:
            raise FlexWebError(f"Flex GetStatement returned an unexpected payload: {content[:300]!r}")
        last_error = _xml_error(root, "Flex statement is not ready")
        logger.info(
            "Flex statement not ready on attempt {}/{}: {}",
            attempt,
            settings.ibkr_flex_max_polls,
            last_error,
        )
        if attempt < settings.ibkr_flex_max_polls:
            time.sleep(settings.ibkr_flex_poll_seconds)

    raise FlexWebError(f"Flex statement was not ready after {settings.ibkr_flex_max_polls} polls: {last_error}")


def _build_url(settings: Settings, endpoint: str, params: dict[str, str | None]) -> str:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    return f"{settings.ibkr_flex_base_url}/{endpoint}?{query}"


def _http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "portfolio-warehouse/0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FlexWebError(f"HTTP {exc.code} from IBKR Flex Web Service: {detail}") from exc
    except URLError as exc:
        raise FlexWebError(f"Could not reach IBKR Flex Web Service: {exc}") from exc


def _parse_xml(content: bytes, context: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise FlexWebError(f"{context} response was not valid XML") from exc


def _xml_text(root: ElementTree.Element, tag: str) -> str | None:
    node = root.find(f".//{tag}")
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _xml_error(root: ElementTree.Element, fallback: str) -> str:
    code = _xml_text(root, "ErrorCode")
    message = _xml_text(root, "ErrorMessage") or _xml_text(root, "Message")
    if code and message:
        return f"{fallback}: {code} {message}"
    return message or fallback


def _looks_like_statement(content: bytes) -> bool:
    sample = content.lstrip()[:100].decode("utf-8", errors="ignore")
    return sample.startswith("BOF,") or sample.startswith('"BOF"') or "\nBOA," in sample


def _statement_filename(configured_name: str) -> str:
    path = Path(configured_name)
    stem = safe_filename(path.stem or "ibkr_flex_statement")
    suffix = path.suffix if path.suffix.lower() == ".csv" else ".csv"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}{suffix}"
