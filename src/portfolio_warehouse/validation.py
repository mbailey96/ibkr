from __future__ import annotations

from decimal import Decimal
from typing import Any

from portfolio_warehouse.db import connect


def run_validation() -> list[str]:
    messages: list[str] = []
    with connect() as conn:
        raw_counts = conn.execute(
            """
            select report_type, count(*) as files, coalesce(sum(row_count), 0) as rows
            from raw.report_file
            group by report_type
            order by report_type
            """
        ).fetchall()
        for row in raw_counts:
            messages.append(f"{row['report_type']}: {row['files']} file(s), {row['rows']} raw row(s)")

        latest = conn.execute("select ending_nav from analytics.v_portfolio_latest").fetchone()
        positions = conn.execute(
            "select coalesce(sum(market_value), 0) as market_value from analytics.v_positions_latest"
        ).fetchone()

        if latest and positions:
            ending_nav = Decimal(latest["ending_nav"])
            market_value = Decimal(positions["market_value"])
            diff = abs(ending_nav - market_value)
            messages.append(f"latest NAV: {ending_nav}; latest position value: {market_value}; difference: {diff}")
            if diff > Decimal("1.00"):
                messages.append("WARNING: latest position value differs from latest NAV by more than GBP 1.00")

    return messages
