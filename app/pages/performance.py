from __future__ import annotations

import pandas as pd
from dash import dcc, html

from components.charts import asset_class_contribution_bar, asset_performance_bar
from components.cards import kpi_card, section
from components.formatting import fmt_currency, fmt_return, pnl_class
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    latest = data["overview_kpis"].iloc[0] if not data["overview_kpis"].empty else {}

    cards = html.Div(
        [
            kpi_card("Portfolio Return", fmt_return(latest.get("since_inception_return")), "Since inception", pnl_class(latest.get("since_inception_return"))),
            kpi_card("One-Month Return", fmt_return(latest.get("one_month_return")), "Latest month", pnl_class(latest.get("one_month_return"))),
            kpi_card("YTD Return", fmt_return(latest.get("ytd_return")), "Flex statement period", pnl_class(latest.get("ytd_return"))),
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
                            html.H3("YTD Asset Contributors"),
                            dcc.Graph(figure=asset_performance_bar(data["asset_performance"])),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.H3("Asset Class Contribution"),
                            dcc.Graph(figure=asset_class_contribution_bar(data["asset_class_contribution"])),
                        ],
                        className="panel",
                    ),
                ],
                className="dashboard-grid two-col",
            ),
            section("Asset Performance", [data_table(data["asset_performance"], "asset-performance-table", page_size=12)]),
            section("Asset Class Contribution", [data_table(data["asset_class_contribution"], "asset-class-contribution-table", page_size=8)]),
            section("Account Performance", [data_table(data["allocation_wrapper"], "account-performance-table", page_size=12)]),
        ],
        className="page",
    )
