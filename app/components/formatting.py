from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pandas as pd


def json_safe_value(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def json_safe_records(df: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {column: json_safe_value(value) for column, value in row.items()}
        for row in df.to_dict("records")
    ]


def as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_currency(value: object, currency: str = "GBP", decimals: int = 0) -> str:
    number = as_float(value)
    if number is None:
        return "-"
    prefix = "£" if currency == "GBP" else f"{currency} "
    if number < 0:
        return f"-{prefix}{abs(number):,.{decimals}f}"
    return f"{prefix}{number:,.{decimals}f}"


def fmt_return(value: object, decimals: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "-"
    return f"{number:+.{decimals}f}%"


def fmt_weight(value: object, decimals: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.{decimals}f}%"


def fmt_number(value: object, decimals: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "-"
    return f"{number:,.{decimals}f}"


def fmt_datetime(value: object) -> str:
    if value is None:
        return "-"
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "-"
    return timestamp.strftime("%d %b %Y %H:%M")


def fmt_date(value: object) -> str:
    if value is None:
        return "-"
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "-"
    return timestamp.strftime("%d %b %Y")


def pnl_class(value: object) -> str:
    number = as_float(value)
    if number is None:
        return "neutral"
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def is_money_column(column: str) -> bool:
    lowered = column.lower()
    if "date" in lowered or lowered.endswith("_at") or "time" in lowered:
        return False
    tokens = (
        "amount",
        "assets",
        "cash",
        "commission",
        "contribution",
        "cost",
        "fee",
        "gross",
        "interest_earned",
        "market_value",
        "money",
        "mtm",
        "nav",
        "net",
        "pnl",
        "price",
        "principal",
        "proceeds",
        "tax",
        "total_interest",
        "unrealized",
        "value",
    )
    return any(token in lowered for token in tokens) and "return" not in lowered and "weight" not in lowered


def is_percent_column(column: str) -> bool:
    lowered = column.lower()
    return "weight" in lowered or "return" in lowered or lowered == "rate" or lowered.endswith("_share_of_nav_change")


def is_pnl_column(column: str) -> bool:
    lowered = column.lower()
    tokens = ("pnl", "return", "active", "unrealized", "mtm", "fee", "commission")
    return any(token in lowered for token in tokens)


def format_display_value(column: str, value: object) -> object:
    if value is None:
        return "-"
    try:
        if pd.isna(value):
            return "-"
    except (TypeError, ValueError):
        pass

    lowered = column.lower()
    if "date" in lowered or lowered.endswith("_at"):
        if "time" in lowered or lowered.endswith("_at"):
            return fmt_datetime(value)
        return fmt_date(value)
    if is_percent_column(column):
        if "weight" in lowered or lowered.endswith("_share_of_nav_change"):
            return fmt_weight(value, decimals=2)
        return fmt_return(value, decimals=2)
    if is_money_column(column):
        return fmt_currency(value, decimals=2)
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return fmt_number(value, decimals=2)
    return json_safe_value(value)


def display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    for column in display.columns:
        display[column] = display[column].map(lambda value, col=column: format_display_value(col, value))
    return display
