from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from sqlalchemy import create_engine

from portfolio_warehouse.settings import get_settings


settings = get_settings()
engine = create_engine(settings.database_url)


def read_sql(query: str) -> pd.DataFrame:
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()


def load_dashboard_data() -> dict[str, pd.DataFrame]:
    return {
        "latest_refresh": read_sql("select * from analytics.v_latest_refresh"),
        "overview_kpis": read_sql("select * from analytics.v_overview_kpis"),
        "portfolio_latest": read_sql("select * from analytics.v_portfolio_latest"),
        "portfolio_value_timeseries": read_sql("select * from analytics.v_portfolio_value_timeseries"),
        "portfolio_value_by_account": read_sql("select * from analytics.v_portfolio_value_by_account"),
        "monthly_growth_attribution": read_sql("select * from analytics.v_monthly_growth_attribution"),
        "allocation_asset": read_sql("select * from analytics.v_asset_allocation_latest order by market_value desc nulls last"),
        "allocation_wrapper": read_sql("select * from analytics.v_current_allocation_by_wrapper order by market_value desc nulls last"),
        "holdings": read_sql("select * from analytics.v_current_holdings order by market_value desc nulls last"),
        "asset_performance": read_sql("select * from analytics.v_asset_performance_ytd order by total_pnl_ytd desc nulls last"),
        "asset_class_contribution": read_sql("select * from analytics.v_asset_class_contribution order by end_of_period_value desc nulls last"),
        "trades": read_sql("select * from analytics.v_trade_display order by trade_datetime desc nulls last"),
        "cashflows": read_sql("select * from analytics.v_cashflow_display order by cash_datetime desc nulls last"),
        "interest": read_sql("select * from analytics.v_interest_display order by value_date desc nulls last"),
        "quality": read_sql("select * from analytics.v_data_quality_checks order by check_name"),
    }
