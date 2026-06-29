from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from portfolio_warehouse.ibkr_csv import detect_report_type, iter_flex_rows, parse_decimal, parse_period


class IbkrCsvTests(unittest.TestCase):
    def test_detect_report_type(self) -> None:
        self.assertEqual(detect_report_type("Trades.csv"), "flex_trades")
        self.assertEqual(detect_report_type("Michael_Bailey_Inception_June_26_2026.csv"), "portfolio_summary")

    def test_repeated_headers_are_skipped(self) -> None:
        text = '"ClientAccountID","TransactionID","Amount"\n"U1","T1","10"\n"ClientAccountID","TransactionID","Amount"\n"U1","T2","20"\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Cash.csv"
            path.write_text(text)
            rows = list(iter_flex_rows(path))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].payload["TransactionID"], "T1")
        self.assertEqual(rows[1].payload["Amount"], "20")

    def test_parse_decimal_and_period(self) -> None:
        self.assertEqual(str(parse_decimal("1,234.50")), "1234.50")
        start, end = parse_period("March 6, 2026 - June 26, 2026")
        self.assertEqual(str(start), "2026-03-06")
        self.assertEqual(str(end), "2026-06-26")


if __name__ == "__main__":
    unittest.main()

