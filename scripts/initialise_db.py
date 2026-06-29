from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_warehouse.db import execute_sql_file


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "sql/000_drop_analytics_views.sql",
        "sql/001_raw_schema.sql",
        "sql/002_staging_schema.sql",
        "sql/003_analytics_schema.sql",
        "sql/020_analytics_views.sql",
    ):
        execute_sql_file(root / relative)
        print(f"applied {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
