from __future__ import annotations

import pandas as pd
from dash import dcc, html

from components.cards import kpi_card, section
from components.charts import monthly_returns_bar
from components.formatting import fmt_currency, fmt_return, pnl_class
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    latest = data["overview_kpis"].iloc[0] if not data["overview_kpis"].empty else {}

    cards = html.Div(
        [
            kpi_card("Portfolio Return", fmt_return(latest.get("since_inception_return")), "Since inception", pnl_class(latest.get("since_inception_return"))),
            kpi_card("One-Month Return", fmt_return(latest.get("one_month_return")), "Latest month", pnl_class(latest.get("one_month_return"))),
            kpi_card("YTD Return", fmt_return(latest.get("ytd_return")), "PortfolioAnalyst period", pnl_class(latest.get("ytd_return"))),
            kpi_card("MTM", fmt_currency(latest.get("mtm"), decimals=2), "Mark-to-market contribution", pnl_class(latest.get("mtm"))),
        ],
        className="kpi-grid compact",
    )

    return html.Div(
        [
            cards,
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Monthly Returns"),
                            dcc.Graph(figure=monthly_returns_bar(data["monthly_returns"])),
                        ],
                        className="panel panel-full",
                    )
                ],
                className="dashboard-grid",
            ),
            section("Benchmark Comparison", [data_table(data["benchmark"], "benchmark-table", page_size=12)]),
        ],
        className="page",
    )
