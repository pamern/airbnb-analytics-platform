from __future__ import annotations

import streamlit as st

from components.executive_overview import render_executive_overview
from components.host_review_quality import render_host_review_quality
from components.location_availability_performance import (
    render_location_availability_performance,
)
from components.pricing_listing_performance import (
    render_pricing_listing_performance,
)


def render_dashboard_page() -> None:
    sections = {
        "Market Overview": "Market Overview",
        "Pricing & Performance": "Pricing & Listing Performance",
        "Location & Availability": "Location & Forward Availability",
        "Host & Review Quality": "Host & Review Quality",
    }
    selected_section = st.segmented_control(
        "Dashboard section",
        options=list(sections.keys()),
        default="Market Overview",
        selection_mode="single",
        width="stretch",
        key="dashboard_section",
    )

    if selected_section is None:
        selected_section = "Market Overview"

    target_section = sections[selected_section]

    if target_section == "Market Overview":
        render_executive_overview()
    elif target_section == "Pricing & Listing Performance":
        render_pricing_listing_performance()
    elif target_section == "Location & Forward Availability":
        render_location_availability_performance()
    elif target_section == "Host & Review Quality":
        render_host_review_quality()
