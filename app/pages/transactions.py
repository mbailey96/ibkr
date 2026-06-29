from __future__ import annotations

import pandas as pd
from dash import html

from components.cards import section
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    return html.Div(
        [
            html.Div(
                "Use the column filters and sort controls in each table for date, account, symbol and type filtering.",
                className="page-note",
            ),
            section("Trades", [data_table(data["trades"], "trades-table", page_size=12)]),
            section("Cashflows", [data_table(data["cashflows"], "cashflows-table", page_size=12)]),
            section("Interest", [data_table(data["interest"], "interest-table", page_size=12)]),
        ],
        className="page",
    )

