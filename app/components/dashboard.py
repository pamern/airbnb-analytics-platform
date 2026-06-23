from __future__ import annotations

import streamlit as st

from app.components.executive_overview import render_executive_overview
from app.components.host_review_quality import render_host_review_quality
from app.components.location_availability_performance import (
    render_location_availability_performance,
)
from app.components.pricing_listing_performance import (
    render_pricing_listing_performance,
)
from app.components.ui import render_section_intro


def render_dashboard_page() -> None:
    sections = [
        "Pricing & Listing Performance",
        "Executive Overview",
        "Location & Availability Performance",
        "Host & Review Quality",
    ]
    selected_section = st.segmented_control(
        "Dashboard section",
        options=sections,
        default="Pricing & Listing Performance",
        selection_mode="single",
    )

    if selected_section is None:
        selected_section = "Pricing & Listing Performance"

    render_section_intro(
        selected_section,
        {
            "Executive Overview": "Tong hop nhanh KPI co ban, market pulse, va inventory mix de mo dau dashboard.",
            "Pricing & Listing Performance": "Phan tich gia niem yet, occupancy uoc tinh, revenue uoc tinh, va watchlist listing theo Gold layer.",
            "Location & Availability Performance": "Theo doi hieu qua theo khu vuc va inventory pressure qua availability.",
            "Host & Review Quality": "Tap trung vao chat luong host, review dimensions, va cac tin hieu anh huong trai nghiem khach.",
        },
    )

    _SPINNER_MESSAGES = {
        "Executive Overview": "Loading executive overview data...",
        "Pricing & Listing Performance": "Loading pricing data...",
        "Location & Availability Performance": "Loading location data...",
        "Host & Review Quality": "Loading host and review data...",
    }

    with st.spinner(_SPINNER_MESSAGES.get(selected_section, "Loading data...")):
        if selected_section == "Executive Overview":
            render_executive_overview()
        elif selected_section == "Pricing & Listing Performance":
            render_pricing_listing_performance()
        elif selected_section == "Location & Availability Performance":
            render_location_availability_performance()
        elif selected_section == "Host & Review Quality":
            render_host_review_quality()
