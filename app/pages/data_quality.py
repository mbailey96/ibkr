from __future__ import annotations

import pandas as pd
from dash import html

from components.cards import kpi_card, section
from components.formatting import fmt_datetime
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    quality = data["quality"]
    refresh = data["latest_refresh"]
    has_refresh = not refresh.empty
    latest = refresh.iloc[0] if not refresh.empty else {}
    statuses = set(quality["status"].dropna().astype(str)) if not quality.empty and "status" in quality else set()
    overall = "FAIL" if "fail" in statuses else "WARNING" if "warning" in statuses else "OK"
    value_class = "negative" if overall == "FAIL" else "warning" if overall == "WARNING" else "positive"

    cards = html.Div(
        [
            kpi_card("Pipeline Status", overall, "Derived from data quality checks", value_class),
            kpi_card("Last Updated", fmt_datetime(latest.get("last_updated_at")), "Latest raw file ingestion"),
            kpi_card("Source Files", str(int(latest.get("source_file_count", 0))) if has_refresh else "-", "Raw IBKR files"),
            kpi_card("Latest Snapshot", fmt_datetime(latest.get("latest_portfolio_summary_at")), "Portfolio summary"),
        ],
        className="kpi-grid compact",
    )

    return html.Div(
        [
            cards,
            section("Checks", [data_table(quality, "quality-table", page_size=20)]),
        ],
        className="page",
    )
