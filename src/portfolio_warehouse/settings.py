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
    email_host: str
    email_port: int
    email_user: str | None
    email_app_password: str | None
    email_folder: str
    email_processed_folder: str
    ibkr_email_from_contains: str
    ibkr_email_subject_contains: tuple[str, ...]
    email_lookback_days: int
    smtp_host: str
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_starttls: bool
    notify_email_from: str | None
    notify_email_to: tuple[str, ...]
    notify_on_success: bool
    pipeline_email_limit: int | None
    schedule_hour: int
    schedule_minute: int


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
        email_host=os.environ.get("EMAIL_HOST", "imap.mail.me.com"),
        email_port=int(os.environ.get("EMAIL_PORT", "993")),
        email_user=email_user,
        email_app_password=email_app_password,
        email_folder=os.environ.get("EMAIL_FOLDER", "INBOX"),
        email_processed_folder=os.environ.get("EMAIL_PROCESSED_FOLDER", "IBKR Processed"),
        ibkr_email_from_contains=os.environ.get(
            "IBKR_EMAIL_FROM_CONTAINS",
            os.environ.get("IBKR_EMAIL_FROM", "interactivebrokers"),
        ),
        ibkr_email_subject_contains=tuple(
            part.strip().lower()
            for part in os.environ.get(
                "IBKR_EMAIL_SUBJECT_CONTAINS",
                "flex,statement,activity,portfolio",
            ).split(",")
            if part.strip()
        ),
        email_lookback_days=int(os.environ.get("EMAIL_LOOKBACK_DAYS", "30")),
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
        notify_on_success=_env_bool("NOTIFY_ON_SUCCESS", False),
        pipeline_email_limit=_env_int_or_none("PIPELINE_EMAIL_LIMIT"),
        schedule_hour=int(os.environ.get("PIPELINE_SCHEDULE_HOUR", "8")),
        schedule_minute=int(os.environ.get("PIPELINE_SCHEDULE_MINUTE", "15")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int_or_none(name: str) -> int | None:
    value = os.environ.get(name)
    if not value:
        return None
    return int(value)
