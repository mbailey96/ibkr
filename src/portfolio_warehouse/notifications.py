from __future__ import annotations

import smtplib
from email.message import EmailMessage

from loguru import logger

from portfolio_warehouse.settings import Settings


def send_notification_email(*, settings: Settings, subject: str, body: str) -> bool:
    if not settings.notify_email_to:
        logger.warning("Notification email skipped: NOTIFY_EMAIL_TO is not configured.")
        return False
    if not settings.notify_email_from:
        logger.warning("Notification email skipped: NOTIFY_EMAIL_FROM is not configured.")
        return False
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("Notification email skipped: SMTP_USER/SMTP_PASSWORD are not configured.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.notify_email_from
    message["To"] = ", ".join(settings.notify_email_to)
    message.set_content(body)

    logger.info("Sending notification email to {}", ", ".join(settings.notify_email_to))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        if settings.smtp_starttls:
            client.starttls()
        client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)
    return True
