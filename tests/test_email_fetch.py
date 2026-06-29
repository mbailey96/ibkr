from __future__ import annotations

import tempfile
import unittest
import zipfile
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

from portfolio_warehouse.email_fetch import _matches_ibkr_message, _save_expected_attachments
from portfolio_warehouse.settings import Settings


def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="postgresql://portfolio:portfolio_dev_password@localhost:55432/portfolio",
        raw_data_dir=tmp_path / "raw",
        inbox_dir=tmp_path / "inbox",
        log_dir=tmp_path / "logs",
        log_level="INFO",
        email_host="imap.mail.me.com",
        email_port=993,
        email_user="user@example.com",
        email_app_password="secret",
        email_folder="INBOX",
        email_processed_folder="IBKR Processed",
        ibkr_email_from_contains="interactivebrokers",
        ibkr_email_subject_contains=("flex", "statement"),
        email_lookback_days=30,
        smtp_host="smtp.mail.me.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="secret",
        smtp_starttls=True,
        notify_email_from="user@example.com",
        notify_email_to=("user@example.com",),
        notify_on_success=False,
        pipeline_email_limit=None,
        schedule_hour=8,
        schedule_minute=15,
    )


class EmailFetchTests(unittest.TestCase):
    def test_matches_ibkr_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = test_settings(Path(tmp))
            message = EmailMessage()
            message["From"] = "Interactive Brokers <statements@interactivebrokers.com>"
            message["Subject"] = "Daily Flex Query Statement"
            self.assertTrue(_matches_ibkr_message(message, settings))

    def test_saves_expected_csv_attachment(self) -> None:
        message = EmailMessage()
        message["From"] = "Interactive Brokers <statements@interactivebrokers.com>"
        message["Subject"] = "Daily Flex Query Statement"
        message["Date"] = "Mon, 29 Jun 2026 08:00:00 +0000"
        message.set_content("Attached")
        message.add_attachment(
            b'"ClientAccountID","TransactionID"\n"U1","T1"\n',
            maintype="text",
            subtype="csv",
            filename="Trades.csv",
        )

        with tempfile.TemporaryDirectory() as tmp:
            saved = _save_expected_attachments(message, uid="123", inbox_dir=Path(tmp), dry_run=False)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].report_type, "flex_trades")
            self.assertTrue(saved[0].stored_path.exists())

    def test_saves_expected_csv_inside_zip_attachment(self) -> None:
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("Cash.csv", '"ClientAccountID","TransactionID"\n"U1","C1"\n')
            archive.writestr("ignored.txt", "ignore")

        message = EmailMessage()
        message["From"] = "Interactive Brokers <statements@interactivebrokers.com>"
        message["Subject"] = "Daily Flex Query Statement"
        message.set_content("Attached")
        message.add_attachment(
            archive_bytes.getvalue(),
            maintype="application",
            subtype="zip",
            filename="ibkr.zip",
        )

        with tempfile.TemporaryDirectory() as tmp:
            saved = _save_expected_attachments(message, uid="124", inbox_dir=Path(tmp), dry_run=False)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].report_type, "flex_cash")
            self.assertTrue(saved[0].stored_path.exists())


if __name__ == "__main__":
    unittest.main()
