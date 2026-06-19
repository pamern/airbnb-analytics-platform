from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


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

        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 1200px;
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
