from __future__ import annotations

import pandas as pd
from dash import dcc, html

from components.cards import kpi_card, section
from components.charts import (
    allocation_bar,
    asset_performance_bar,
    monthly_attribution_bar,
    nav_change_breakdown_bar,
    portfolio_value_by_account_line,
    portfolio_value_line,
)
from components.formatting import fmt_currency, fmt_return, fmt_weight, pnl_class
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    kpis = data["overview_kpis"]
    latest = kpis.iloc[0] if not kpis.empty else {}

    cards = html.Div(
        [
            kpi_card(
                "Total Investable Assets",
                fmt_currency(latest.get("total_investable_assets"), decimals=2),
                "Latest Flex NAV",
            ),
            kpi_card(
                "Month Return",
                fmt_return(latest.get("one_month_return")),
                "Latest one-month return",
                pnl_class(latest.get("one_month_return")),
            ),
            kpi_card(
                "YTD Return",
                fmt_return(latest.get("ytd_return")),
                "Current report period",
                pnl_class(latest.get("ytd_return")),
            ),
            kpi_card(
                "Since Inception",
                fmt_return(latest.get("since_inception_return")),
                "Portfolio return",
                pnl_class(latest.get("since_inception_return")),
            ),
            kpi_card(
                "Contributions",
                fmt_currency(latest.get("total_contributions"), decimals=2),
                "Deposits less withdrawals",
            ),
            kpi_card(
                "Investment Return",
                fmt_currency(latest.get("investment_return"), decimals=2),
                "Market movement",
                pnl_class(latest.get("investment_return")),
            ),
            kpi_card(
                "Cash Weight",
                fmt_weight(latest.get("cash_weight")),
                fmt_currency(latest.get("cash_value"), decimals=2),
            ),
        ],
        className="kpi-grid",
    )

    charts = html.Div(
        [
            html.Div(
                [
                    html.H3("Portfolio Value"),
                    dcc.Graph(figure=portfolio_value_line(data["portfolio_value_timeseries"])),
                ],
                className="panel panel-wide",
            ),
            html.Div(
                [
                    html.H3("NAV By Account"),
                    dcc.Graph(figure=portfolio_value_by_account_line(data["portfolio_value_by_account"])),
                ],
                className="panel panel-wide",
            ),
            html.Div(
                [
                    html.H3("Top Asset Contributors"),
                    dcc.Graph(figure=asset_performance_bar(data["asset_performance"])),
                ],
                className="panel panel-wide",
            ),
            html.Div(
                [
                    html.H3("Current Allocation"),
                    dcc.Graph(figure=allocation_bar(data["allocation_asset"])),
                ],
                className="panel",
            ),
            html.Div(
                [
                    html.H3("Source Of NAV Change"),
                    dcc.Graph(figure=nav_change_breakdown_bar(data["overview_kpis"])),
                ],
                className="panel panel-full",
            ),
            html.Div(
                [
                    html.H3("Cashflow Attribution"),
                    dcc.Graph(figure=monthly_attribution_bar(data["monthly_growth_attribution"])),
                ],
                className="panel panel-full",
            ),
        ],
        className="dashboard-grid",
    )

    return html.Div(
        [
            cards,
            charts,
            section("Current Holdings", [data_table(data["holdings"], "overview-holdings", page_size=8)]),
        ],
        className="page",
    )
