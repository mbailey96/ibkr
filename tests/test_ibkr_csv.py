from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from portfolio_warehouse.ibkr_csv import detect_report_type, iter_flex_section_rows, parse_date, parse_decimal


class IbkrCsvTests(unittest.TestCase):
    def test_sectioned_flex_rows_are_parsed(self) -> None:
        text = "\n".join(
            [
                '"BOF","U1","All","1","2026-01-01"',
                '"BOA","U1"',
                '"BOS","TRNT","Trades; trade date basis"',
                '"HEADER","TRNT","ClientAccountID","TransactionID","Amount"',
                '"DATA","TRNT","U1","T1","10"',
                '"EOS","TRNT","1","10"',
                '"EOA","U1"',
                '"EOF"',
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "All.csv"
            path.write_text(text)
            self.assertEqual(detect_report_type(path), "flex_statement")
            rows = list(iter_flex_section_rows(path))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].account_id, "U1")
        self.assertEqual(rows[0].section_code, "TRNT")
        self.assertEqual(rows[0].payload["TransactionID"], "T1")

    def test_rejects_non_sectioned_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flat.csv"
            path.write_text('"ClientAccountID","TransactionID","Amount"\n"U1","T1","10"\n')
            with self.assertRaises(ValueError):
                detect_report_type(path)

    def test_parse_decimal_and_date(self) -> None:
        self.assertEqual(str(parse_decimal("1,234.50")), "1234.50")
        self.assertEqual(str(parse_date("2026-06-26")), "2026-06-26")


if __name__ == "__main__":
    unittest.main()
