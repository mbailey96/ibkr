from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_url: str
    raw_data_dir: Path
    inbox_dir: Path
    log_dir: Path
    log_level: str
    smtp_host: str
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_starttls: bool
    notify_email_from: str | None
    notify_email_to: tuple[str, ...]
    ibkr_flex_token: str | None = None
    ibkr_flex_query_id: str | None = None
    ibkr_flex_base_url: str = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
    ibkr_flex_api_version: int = 3
    ibkr_flex_poll_seconds: float = 5
    ibkr_flex_max_polls: int = 12
    ibkr_flex_output_name: str = "ibkr_flex_statement.csv"
    pipeline_fetch_source: str = "flex"
    schedule_hour: int = 8
    schedule_minute: int = 15


def get_settings() -> Settings:
    load_dotenv()
    email_user = os.environ.get("EMAIL_USER")
    email_app_password = os.environ.get("EMAIL_APP_PASSWORD")
    smtp_user = os.environ.get("SMTP_USER", email_user)
    smtp_password = os.environ.get("SMTP_PASSWORD", email_app_password)
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://portfolio:portfolio_dev_password@localhost:55432/portfolio",
        ),
        raw_data_dir=Path(os.environ.get("RAW_DATA_DIR", "./data/raw")),
        inbox_dir=Path(os.environ.get("INBOX_DIR", "./data/inbox")),
        log_dir=Path(os.environ.get("LOG_DIR", "./logs")),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        smtp_host=os.environ.get("SMTP_HOST", "smtp.mail.me.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_starttls=_env_bool("SMTP_STARTTLS", True),
        notify_email_from=os.environ.get("NOTIFY_EMAIL_FROM", smtp_user or email_user),
        notify_email_to=tuple(
            part.strip()
            for part in os.environ.get("NOTIFY_EMAIL_TO", email_user or "").split(",")
            if part.strip()
        ),
        ibkr_flex_token=os.environ.get("IBKR_FLEX_TOKEN") or os.environ.get("IBKR_FLEX_WEB_TOKEN"),
        ibkr_flex_query_id=os.environ.get("IBKR_FLEX_QUERY_ID"),
        ibkr_flex_base_url=os.environ.get(
            "IBKR_FLEX_BASE_URL",
            "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService",
        ).rstrip("/"),
        ibkr_flex_api_version=int(os.environ.get("IBKR_FLEX_API_VERSION", "3")),
        ibkr_flex_poll_seconds=float(os.environ.get("IBKR_FLEX_POLL_SECONDS", "5")),
        ibkr_flex_max_polls=int(os.environ.get("IBKR_FLEX_MAX_POLLS", "12")),
        ibkr_flex_output_name=os.environ.get("IBKR_FLEX_OUTPUT_NAME", "ibkr_flex_statement.csv"),
        pipeline_fetch_source=os.environ.get("PIPELINE_FETCH_SOURCE", "flex").strip().lower(),
        schedule_hour=int(os.environ.get("PIPELINE_SCHEDULE_HOUR", "8")),
        schedule_minute=int(os.environ.get("PIPELINE_SCHEDULE_MINUTE", "15")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
