from __future__ import annotations

from dash import dcc, html

from components.header import app_header
from data import load_dashboard_data
from pages import allocation, data_quality, overview, performance, transactions


def build_layout() -> html.Main:
    data = load_dashboard_data()
    return html.Main(
        [
            app_header(data["latest_refresh"], data["quality"]),
            dcc.Tabs(
                [
                    dcc.Tab(label="Overview", children=overview.render(data)),
                    dcc.Tab(label="Performance", children=performance.render(data)),
                    dcc.Tab(label="Allocation", children=allocation.render(data)),
                    dcc.Tab(label="Transactions", children=transactions.render(data)),
                    dcc.Tab(label="Data Quality", children=data_quality.render(data)),
                ],
                className="tabs",
                parent_className="tabs-container",
            ),
            html.Footer("Local IBKR portfolio warehouse", className="app-footer"),
        ],
        className="app-shell",
    )

