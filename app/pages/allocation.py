from __future__ import annotations

import pandas as pd
from dash import dcc, html

from components.cards import section
from components.charts import allocation_bar
from components.tables import data_table


def render(data: dict[str, pd.DataFrame]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Allocation By Asset"),
                            dcc.Graph(figure=allocation_bar(data["allocation_asset"])),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.H3("Allocation By Wrapper"),
                            dcc.Graph(figure=allocation_bar(data["allocation_wrapper"])),
                        ],
                        className="panel",
                    ),
                ],
                className="dashboard-grid two-col",
            ),
            section("Wrapper Allocation", [data_table(data["allocation_wrapper"], "wrapper-table", page_size=8)]),
            section("Current Holdings", [data_table(data["holdings"], "allocation-holdings", page_size=12)]),
        ],
        className="page",
    )

