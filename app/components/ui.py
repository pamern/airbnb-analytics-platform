from __future__ import annotations

from html import escape
from typing import Any, Sequence

import streamlit as st

DEFAULT_PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
}


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap");

        html, body, [class*="css"] {
            font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
        }

        /* hide deploy button and top decoration */
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"] {
            display: none !important;
        }

        /* hide the close button — sidebar stays open permanently */
        div[data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] button[kind="header"] {
            display: none !important;
        }

        /* if sidebar somehow collapses, force it back open */
        section[data-testid="stSidebar"] {
            left: 0 !important;
            transform: translateX(0) !important;
            min-width: 244px !important;
        }

        header[data-testid="stHeader"] {
            height: 0 !important;
            min-height: 0 !important;
        }

        div[data-testid="stAppViewBlockContainer"] h1 {
            font-size: 3.2rem !important;
            line-height: 1.05 !important;
            font-weight: 700 !important;
            margin-top: 0.15rem !important;
            margin-bottom: 0.35rem !important;
        }

        div[data-testid="stAppViewBlockContainer"] h3 {
            font-size: 1.15rem !important;
            line-height: 1.3 !important;
            margin-top: 0.1rem !important;
            margin-bottom: 0.35rem !important;
            font-weight: 600 !important;
        }

        div[data-testid="stAppViewBlockContainer"] h4 {
            font-size: 1.05rem !important;
            line-height: 1.3 !important;
            margin-top: 0.2rem !important;
            margin-bottom: 0.35rem !important;
            font-weight: 600 !important;
        }

        div[data-testid="stAppViewBlockContainer"] p {
            margin-top: 0.15rem !important;
            margin-bottom: 0.45rem !important;
        }

        div[data-testid="stCaptionContainer"] p,
        [data-testid="stCaptionContainer"] p {
            font-size: 0.84rem !important;
            line-height: 1.45 !important;
            color: #5B6573 !important;
            margin-top: 0.1rem !important;
            margin-bottom: 0.4rem !important;
        }

        div[data-testid="stAppViewBlockContainer"] hr {
            margin-top: 0.75rem !important;
            margin-bottom: 0.75rem !important;
        }

        .block-container {
            padding-top: 0.2rem !important;
            padding-bottom: 2rem !important;
            max-width: 1800px;
            width: 100%;
        }

        div[data-testid="stMetric"] {
            min-height: 108px;
        }

        div[data-testid="stMetricLabel"] p {
            font-size: 0.94rem !important;
            line-height: 1.25 !important;
            font-weight: 500 !important;
            white-space: normal !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 2.35rem !important;
            line-height: 1.05 !important;
        }

        div[data-testid="stMetricValue"] > div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            word-break: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, kicker: str = "Airbnb Analytics") -> None:
    st.markdown(f"**{escape(kicker).upper()}**")
    st.title(title)
    st.caption(subtitle)
    st.divider()


def format_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float) and value != value:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:,.{digits}f}"
    return str(value)


def render_section_intro(section: str, descriptions: dict[str, str]) -> None:
    st.caption(descriptions[section])


def render_metric_grid(
    metrics: Sequence[dict[str, Any]],
    cards_per_row: int = 3,
) -> None:
    if cards_per_row <= 0:
        raise ValueError("cards_per_row must be greater than 0")

    for start in range(0, len(metrics), cards_per_row):
        row_metrics = metrics[start:start + cards_per_row]
        columns = st.columns(cards_per_row)
        for column, metric in zip(columns, row_metrics):
            with column:
                st.metric(
                    metric["label"],
                    metric["value"],
                    help=metric.get("help"),
                )
                if metric.get("caption"):
                    st.caption(metric["caption"])


def two_column_layout(spec: Sequence[float]) -> tuple[Any, Any]:
    return st.columns(spec)
