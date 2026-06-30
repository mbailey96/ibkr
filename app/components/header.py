from __future__ import annotations

import pandas as pd
from dash import html

from components.formatting import fmt_date, fmt_datetime


def app_header(refresh: pd.DataFrame, quality: pd.DataFrame) -> html.Header:
    last_updated = "-"
    data_period = "-"
    latest_snapshot = "-"
    status = "OK"

    if not refresh.empty:
        row = refresh.iloc[0]
        last_updated = fmt_datetime(row.get("last_updated_at"))
        start = fmt_date(row.get("earliest_period_start"))
        end = fmt_date(row.get("latest_period_end"))
        data_period = f"{start} -> {end}" if start != "-" or end != "-" else "-"
        latest_snapshot = end

    if not quality.empty and "status" in quality:
        statuses = set(quality["status"].dropna().astype(str))
        if "fail" in statuses:
            status = "FAIL"
        elif "warning" in statuses:
            status = "WARNING"

    return html.Header(
        [
            html.Div(
                [
                    html.H1("Michael Portfolio Dashboard"),
                    html.Div("IBKR Portfolio Warehouse", className="header-subtitle"),
                ],
                className="header-left",
            ),
            html.Div(
                [
                    html.Div(f"Last updated: {last_updated}"),
                    html.Div(f"Data period: {data_period}"),
                    html.Div(
                        [
                            html.Span("DB: local", className="badge"),
                            html.Span(f"Status: {status}", className=f"badge status-{status.lower()}"),
                            html.Span(f"Latest snapshot: {latest_snapshot}", className="badge"),
                        ],
                        className="badge-row",
                    ),
                    html.Button("Reload From IBKR", id="refresh-data-button", n_clicks=0, className="refresh-button"),
                ],
                className="header-right",
            ),
        ],
        className="app-header",
    )
