from __future__ import annotations

from dash import dcc, html

from components.header import app_header
from data import load_dashboard_data
from pages import allocation, data_quality, overview, performance, transactions


def build_tabs(data: dict) -> dcc.Tabs:
    return dcc.Tabs(
        [
            dcc.Tab(label="Overview", children=overview.render(data)),
            dcc.Tab(label="Performance", children=performance.render(data)),
            dcc.Tab(label="Allocation", children=allocation.render(data)),
            dcc.Tab(label="Transactions", children=transactions.render(data)),
            dcc.Tab(label="Data Quality", children=data_quality.render(data)),
        ],
        className="tabs",
        parent_className="tabs-container",
    )


def build_layout() -> html.Main:
    data = load_dashboard_data()
    return html.Main(
        [
            html.Div(app_header(data["latest_refresh"], data["quality"]), id="header-container"),
            html.Div(id="refresh-status", className="refresh-status"),
            html.Div(build_tabs(data), id="tabs-content"),
            html.Footer("Local IBKR portfolio warehouse", className="app-footer"),
        ],
        className="app-shell",
    )
