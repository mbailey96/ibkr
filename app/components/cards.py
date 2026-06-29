from __future__ import annotations

from dash import html


def kpi_card(title: str, value: str, subtitle: str = "", value_class: str = "neutral") -> html.Div:
    return html.Div(
        [
            html.Div(title, className="kpi-title"),
            html.Div(value, className=f"kpi-value {value_class}"),
            html.Div(subtitle, className="kpi-subtitle"),
        ],
        className="kpi-card",
    )


def section(title: str, children: list[object], class_name: str = "") -> html.Section:
    classes = "section"
    if class_name:
        classes = f"{classes} {class_name}"
    return html.Section([html.H2(title), *children], className=classes)

