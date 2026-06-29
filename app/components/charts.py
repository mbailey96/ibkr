from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go


def empty_figure(message: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper")
    return _style(fig)


def allocation_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "market_value" not in df:
        return empty_figure()
    label_col = "financial_instrument" if "financial_instrument" in df else "wrapper"
    plot_df = df.sort_values("market_value", ascending=True).tail(12)
    fig = go.Figure(
        go.Bar(
            x=plot_df["market_value"],
            y=plot_df[label_col],
            orientation="h",
            marker_color="#1f4e79",
            hovertemplate="%{y}<br>£%{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="Market value", yaxis_title="")
    return _style(fig)


def portfolio_value_line(df: pd.DataFrame) -> go.Figure:
    if df.empty or "as_of_date" not in df or "ending_nav" not in df:
        return empty_figure("Portfolio history will appear after reports accumulate")
    fig = go.Figure(
        go.Scatter(
            x=df["as_of_date"],
            y=df["ending_nav"],
            mode="lines+markers",
            line={"color": "#1f4e79", "width": 3},
            hovertemplate="%{x}<br>£%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="", yaxis_title="NAV")
    return _style(fig)


def monthly_attribution_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "month_start" not in df:
        return empty_figure("Monthly attribution will appear after cashflows accumulate")
    fig = go.Figure()
    actual_values: list[float] = []
    series = [
        ("contributions", "#1f4e79"),
        ("interest", "#14804a"),
        ("fees", "#b42318"),
        ("other_cashflows", "#667085"),
    ]
    for column, color in series:
        if column in df:
            actual = pd.to_numeric(df[column], errors="coerce").fillna(0)
            actual_values.extend(actual.tolist())
            fig.add_bar(
                name=column.replace("_", " ").title(),
                x=df["month_start"],
                y=_signed_log_series(actual),
                customdata=actual,
                hovertext=actual.map(_currency_hover),
                marker_color=color,
                hovertemplate="%{x}<br>%{hovertext}<extra>%{fullData.name}</extra>",
            )
    fig.update_layout(barmode="group", xaxis_title="")
    _apply_signed_log_axis(fig, actual_values, "Cashflow")
    return _style(fig)


def nav_change_breakdown_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("NAV change attribution will appear after PortfolioAnalyst data loads")
    row = df.iloc[0]
    values = {
        "Contributions": row.get("total_contributions"),
        "Investment return": row.get("investment_return"),
        "Interest": row.get("interest_earned"),
        "Fees": row.get("fees_paid"),
        "Other": row.get("other_change"),
    }
    plot_df = pd.DataFrame(
        [
            {"source": key, "value": float(value)}
            for key, value in values.items()
            if pd.notna(value)
        ]
    )
    if plot_df.empty:
        return empty_figure("NAV change attribution will appear after PortfolioAnalyst data loads")
    colors = ["#14804a" if value >= 0 else "#b42318" for value in plot_df["value"]]
    fig = go.Figure(
        go.Bar(
            x=plot_df["source"],
            y=_signed_log_series(plot_df["value"]),
            customdata=plot_df["value"],
            hovertext=plot_df["value"].map(_currency_hover),
            marker_color=colors,
            hovertemplate="%{x}<br>%{hovertext}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="")
    _apply_signed_log_axis(fig, plot_df["value"].tolist(), "NAV change")
    return _style(fig)


def monthly_returns_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "month_label" not in df:
        return empty_figure("Monthly returns will appear after benchmark data accumulates")
    fig = go.Figure()
    if "account_return" in df:
        fig.add_bar(name="Portfolio", x=df["month_label"], y=df["account_return"], marker_color="#1f4e79")
    if "bm1_return" in df:
        fig.add_bar(name="BM1", x=df["month_label"], y=df["bm1_return"], marker_color="#667085")
    fig.update_layout(barmode="group", xaxis_title="", yaxis_title="Return %")
    return _style(fig)


def _style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        margin={"l": 24, "r": 16, "t": 24, "b": 32},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "system-ui, -apple-system, BlinkMacSystemFont, sans-serif", "color": "#172033"},
        legend={"orientation": "h", "y": -0.2},
    )
    return fig


def _signed_log_value(value: object) -> float:
    number = float(value or 0)
    if number == 0:
        return 0
    return math.copysign(math.log10(1 + abs(number)), number)


def _signed_log_series(values: pd.Series) -> pd.Series:
    return values.map(_signed_log_value)


def _apply_signed_log_axis(fig: go.Figure, values: list[float], title: str) -> None:
    max_abs = max((abs(float(value)) for value in values if pd.notna(value)), default=0)
    ticks = [0]
    if max_abs > 0:
        max_power = math.ceil(math.log10(max_abs))
        positive_ticks = [10**power for power in range(0, max_power + 1)]
        ticks = [-tick for tick in reversed(positive_ticks)] + [0] + positive_ticks
    tick_values = [_signed_log_value(value) for value in ticks]
    fig.update_yaxes(
        title=f"{title} (signed log £)",
        tickmode="array",
        tickvals=tick_values,
        ticktext=[_currency_tick(value) for value in ticks],
        zeroline=True,
        zerolinecolor="#98a2b3",
        zerolinewidth=1,
    )


def _currency_tick(value: int) -> str:
    if value == 0:
        return "£0"
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"{sign}£{absolute / 1_000_000:g}m"
    if absolute >= 1_000:
        return f"{sign}£{absolute / 1_000:g}k"
    return f"{sign}£{absolute:g}"


def _currency_hover(value: object) -> str:
    number = float(value or 0)
    if number < 0:
        return f"-£{abs(number):,.2f}"
    return f"£{number:,.2f}"
