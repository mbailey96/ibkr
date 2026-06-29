from __future__ import annotations

import pandas as pd
from dash import dash_table, html

from components.formatting import as_float, display_dataframe, is_money_column, is_percent_column, is_pnl_column, json_safe_records


def data_table(df: pd.DataFrame, table_id: str, page_size: int = 12) -> html.Div:
    if df.empty:
        return html.Div("No rows available.", className="empty-state")

    raw_display = df.copy()
    if len(raw_display) > 500:
        raw_display = raw_display.head(500)
    display = display_dataframe(raw_display)

    style_data_conditional = [
        {
            "if": {"row_index": "odd"},
            "backgroundColor": "#fbfcfe",
        }
    ]
    for display_index, (_, row) in enumerate(raw_display.iterrows()):
        for column in raw_display.columns:
            if not is_pnl_column(column):
                continue
            number = as_float(row[column])
            if number is None or number == 0:
                continue
            style_data_conditional.append(
                {
                    "if": {"row_index": display_index, "column_id": column},
                    "color": "#14804a" if number > 0 else "#b42318",
                    "fontWeight": "650",
                }
            )

    for column in raw_display.columns:
        if is_money_column(column) or is_percent_column(column):
            style_data_conditional.append(
                {
                    "if": {"column_id": column},
                    "textAlign": "right",
                    "fontVariantNumeric": "tabular-nums",
                }
            )

    return dash_table.DataTable(
        id=table_id,
        data=json_safe_records(display),
        columns=[{"name": column.replace("_", " ").title(), "id": column} for column in display.columns],
        page_size=page_size,
        filter_action="native",
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            "fontSize": 13,
            "padding": "8px",
            "textAlign": "left",
            "minWidth": "110px",
            "maxWidth": "320px",
            "whiteSpace": "normal",
        },
        style_header={
            "fontWeight": "700",
            "backgroundColor": "#f8fafc",
            "borderBottom": "1px solid #d0d5dd",
        },
        style_data_conditional=style_data_conditional,
    )
