from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dash import Dash, Input, Output, no_update
from flask import send_from_directory
from loguru import logger

from components.header import app_header
from data import load_dashboard_data
from layout import build_layout, build_tabs
from portfolio_warehouse.pipeline import run_pipeline
from portfolio_warehouse.settings import get_settings


app = Dash(__name__)
app.title = "Michael Portfolio Dashboard"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png?v=2">
        <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16.png?v=2">
        <link rel="shortcut icon" type="image/x-icon" href="/favicon.ico?v=2">
        <link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png?v=2">
        <link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png?v=2">
        <link rel="manifest" href="/assets/manifest.json?v=2">
        <meta name="apple-mobile-web-app-title" content="Portfolio">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#102e39">
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""
app.layout = build_layout


@app.server.route("/favicon.ico")
def favicon():
    return send_from_directory(ASSETS_DIR, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.callback(
    Output("header-container", "children"),
    Output("tabs-content", "children"),
    Output("refresh-status", "children"),
    Input("refresh-data-button", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_from_ibkr(n_clicks: int):
    if not n_clicks:
        return no_update, no_update, no_update
    try:
        settings = get_settings()
        result = run_pipeline(settings=settings)
        data = load_dashboard_data()
        message = (
            "Reload complete: "
            f"downloaded {result.downloaded_files}, "
            f"ingested {result.ingested_count}, "
            f"skipped {result.skipped_count}."
        )
        return app_header(data["latest_refresh"], data["quality"]), build_tabs(data), message
    except Exception as exc:
        logger.exception("Dashboard-triggered IBKR reload failed")
        return no_update, no_update, f"Reload failed: {exc}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    app.run(host="0.0.0.0", port=port, debug=True)
