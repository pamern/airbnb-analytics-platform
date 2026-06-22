from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from data_access import load_model3_dropdown_options
from services.model3_kmeans_service import (
    MOCK_PREDICTED_PRICE,
    analyze_user_listing,
    build_cluster_visualization_figure,
)


SEGMENT_DESCRIPTIONS = {
    0: {
        "title": "Standard short-stay listings",
        "body": (
            "The largest segment. Primarily entire homes/apartments attracting 2-guest bookings with 1 bedroom, "
            "1 bathroom, and 1 bed. Moderate amenities and 1-night minimum stay policy. Well-suited for city "
            "travelers and weekend getaways."
        ),
        "tone": "mint",
    },
    1: {
        "title": "Long-stay standard apartments",
        "body": (
            "Focused on long-term rentals with extended minimum stay requirements. Mostly entire homes/apartments "
            "and condos offering compact layouts for 2 guests. Key differentiator: higher minimum_nights policy "
            "targeting business travelers and extended stays."
        ),
        "tone": "warm",
    },
    2: {
        "title": "Large short-stay group homes",
        "body": (
            "Premium larger properties with multiple bedrooms suitable for groups. Houses and homes dominate this "
            "segment with higher capacity and more amenities. Shorter minimum stays attract large family groups "
            "and multi-guest bookings."
        ),
        "tone": "blue",
    },
}


def render_model3_kmeans_page() -> None:
    _inject_model3_styles()
    st.markdown("### Model 3: Price Forecast")
    st.caption(
        "Predict Airbnb rental prices based on KMeans clustering and regression analysis. "
        "This phase uses KMeans to assign property segments; price forecast is currently a mock value."
    )

    result = st.session_state.get("model3_result")
    with st.container(border=True):
        st.markdown('<div class="model3-panel-title">Input Information</div>', unsafe_allow_html=True)
        payload = _render_input_form()

    if payload:
        try:
            st.session_state.model3_result = analyze_user_listing(payload)
        except Exception as exc:
            st.error(f"Cannot run KMeans segment analysis.\n\nError: {exc}")
        result = st.session_state.get("model3_result")

    left, right = st.columns([0.86, 1.78])
    with left:
        _render_result_column(result)
    with right:
        _render_cluster_analytics()


def _render_input_form() -> dict[str, Any]:
    options = _load_options_safely()
    with st.form("model3_kmeans_form"):
        basic, review, host = st.columns([1, 1, 1])
        with basic:
            st.caption("Basic Information")
            neighbourhood = st.selectbox(
                "Neighbourhood",
                options["neighbourhoods"],
                index=_option_index(options["neighbourhoods"], "Ratchathewi"),
            )
            room_type = st.selectbox(
                "Room Type",
                options["room_types"],
                index=_option_index(options["room_types"], "Entire home/apt"),
            )
            property_type = st.selectbox(
                "Property Type",
                options["property_types"],
                index=_option_index(options["property_types"], "Entire condo"),
            )
            cap_a, cap_b = st.columns(2)
            with cap_a:
                accommodates = st.number_input("Accommodates", 1, 30, 2)
                bathrooms = st.number_input("Bathrooms", 0.0, 20.0, 1.0, step=0.5)
            with cap_b:
                bedrooms = st.number_input("Bedrooms", 0.0, 20.0, 1.0, step=1.0)
                beds = st.number_input("Beds", 0.0, 40.0, 1.0, step=1.0)

        with review:
            st.caption("Review Information")
            number_of_reviews = st.number_input("Number of Reviews", 0, 10000, 45)
            r1, r2 = st.columns(2)
            with r1:
                reviews_per_month = st.number_input("Reviews per Month", 0.0, 100.0, 1.5, step=0.1)
                amenities_count = st.number_input("Amenities Count", 0, 300, 15)
            with r2:
                review_score_rating = st.number_input(
                    "Review Score Rating",
                    0.0,
                    5.0,
                    4.8,
                    step=0.1,
                )
                minimum_nights = st.number_input("Minimum Nights", 1, 1125, 2)

        with host:
            st.caption("Host Information & Policy")
            superhost = st.toggle("Superhost", value=True)
            instant_bookable = st.toggle("Instant Bookable", value=False)
            st.markdown('<div class="model3-submit-spacer"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("Predict Price", width="stretch")

    if not submitted:
        return {}
    return {
        "neighbourhood": neighbourhood,
        "room_type": room_type,
        "property_type": property_type,
        "accommodates": accommodates,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "beds": beds,
        "amenities_count": amenities_count,
        "minimum_nights": minimum_nights,
        "number_of_reviews": number_of_reviews,
        "reviews_per_month": reviews_per_month,
        "review_score_rating": review_score_rating,
        "superhost": superhost,
        "instant_bookable": instant_bookable,
        "price": MOCK_PREDICTED_PRICE,
    }


def _render_result_column(result: dict[str, Any] | None) -> None:
    if result is None:
        result = _empty_result()
    segment = escape(str(result["segment_name"]))
    position = escape(str(result["price_position"]))
    delta = _format_signed_pct(result.get("price_vs_segment_median"))

    # Toggle state for details section
    if "show_details" not in st.session_state:
        st.session_state.show_details = False

    st.markdown(
        f"""
        <div class="model3-result-card">
            <div class="model3-result-label">Forecast Result</div>
            <div class="model3-price-row">
                <span class="model3-price">{_format_number(result["current_price"])}</span>
                <span class="model3-price-unit">THB/night</span>
            </div>
            <div class="model3-result-divider"></div>
            <div class="model3-result-pair-grid">
                <div>
                    <div class="model3-mini-label">Segment Average</div>
                    <div class="model3-mini-value">{_format_number(result["segment_mean_price"])} THB</div>
                </div>
                <div>
                    <div class="model3-mini-label">Market Difference</div>
                    <div class="model3-mini-value model3-positive">{delta}</div>
                </div>
            </div>
            <div class="model3-segment-box">
                <div class="model3-mini-label">Segment</div>
                <div class="model3-segment-name">{segment}</div>
                <div class="model3-segment-line">
                    <span>Segment Median:</span>
                    <strong>{_format_number(result["segment_median_price"])} THB</strong>
                </div>
                <div class="model3-mini-label model3-price-position-label">Price Position</div>
                <div class="model3-segment-line">
                    <strong>{position}</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Details button centered below the card
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("View Details", key="details_btn", use_container_width=True):
            st.session_state.show_details = not st.session_state.show_details

    # Show detailed stats when toggled
    if st.session_state.show_details:
        st.markdown(
            f"""
            <div class="model3-stat-table">
                <div><span>Median Price:</span><strong>{_format_decimal(result["segment_median_price"])}</strong></div>
                <div><span>P25 / P75:</span><strong>{_format_number(result["segment_p25_price"])} / {_format_number(result["segment_p75_price"])}</strong></div>
                <div><span>Mean Price:</span><strong>{_format_decimal(result["segment_mean_price"])}</strong></div>
                <div><span>Vs Median:</span><strong>{_format_decimal(result["price_vs_segment_median"], 4)}</strong></div>
                <div><span>Percentile:</span><strong>{_format_pct(result["price_percentile_in_segment"])}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="model3-ai-box">
            <div class="model3-ai-title">AI Recommendation</div>
            <div class="model3-ai-body">
                Based on cluster analysis, your listing belongs to Cluster 0. To increase revenue,
                consider adjusting minimum_nights policy or upgrading amenities to transition into
                Cluster 1, which commands 15% higher average pricing.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cluster_analytics() -> None:
    with st.container(border=True):
        st.markdown("#### K-Means Cluster Analytics")
        try:
            fig = build_cluster_visualization_figure()
            st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:
            st.warning(
                "📊 Cluster visualization not available yet.\n\n"
                "Run `uv run dbt build --project-dir dbt` to generate the gold layer first."
            )

        cols = st.columns(3)
        for index, (cluster_id, details) in enumerate(SEGMENT_DESCRIPTIONS.items()):
            with cols[index]:
                _render_segment_card(cluster_id, details)


def _render_segment_card(cluster_id: int, details: dict[str, str]) -> None:
    st.markdown(
        f"""
        <div class="model3-segment-desc model3-tone-{escape(details["tone"])}">
            <div class="model3-dot-row">
                <span class="model3-dot"></span>
                <span>{escape(details["title"])}</span>
            </div>
            <div class="model3-desc-title">{escape(SEGMENT_DESCRIPTIONS[cluster_id]["title"])}</div>
            <div class="model3-desc-body">{escape(details["body"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _load_options_safely() -> dict[str, list[str]]:
    fallback = {
        "neighbourhoods": ["UNKNOWN"],
        "room_types": ["Entire home/apt", "Private room", "Hotel room", "Shared room"],
        "property_types": ["Entire condo", "Entire rental unit", "Private room", "Entire home"],
    }
    try:
        options = load_model3_dropdown_options()
    except Exception as exc:
        st.warning(f"Cannot load Model 3 dropdown options from silver.silver_listings: {exc}")
        return fallback
    return {
        key: values if values else fallback[key]
        for key, values in options.items()
    }


def _empty_result() -> dict[str, Any]:
    return {
        "cluster": 0,
        "segment_name": "Waiting for prediction",
        "current_price": MOCK_PREDICTED_PRICE,
        "segment_median_price": 0.0,
        "segment_p25_price": 0.0,
        "segment_p75_price": 0.0,
        "segment_mean_price": 0.0,
        "price_vs_segment_median": 0.0,
        "price_percentile_in_segment": 0.0,
        "price_position": "Submit input to assign segment",
    }


def _option_index(options: list[str], preferred: str) -> int:
    return options.index(preferred) if preferred in options else 0


def _format_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.0f}"


def _format_decimal(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.{digits}f}"


def _format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.2%}"


def _format_signed_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):+.1%}"


def _inject_model3_styles() -> None:
    st.markdown(
        """
        <style>
        .model3-panel-title {
            color: #0057B8;
            font-weight: 700;
            font-size: 1.15rem;
            margin-bottom: 1rem;
        }
        .model3-submit-spacer {
            height: 7.7rem;
        }
        .model3-result-card {
            background: #062A5B;
            color: #FFFFFF;
            padding: 1.35rem 1.4rem;
            border: 1px solid #0F2742;
            box-shadow: 0 8px 20px rgba(15, 39, 66, 0.08);
        }
        .model3-result-label,
        .model3-mini-label {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            line-height: 1.25;
        }
        .model3-price-row {
            display: flex;
            align-items: flex-end;
            gap: 0.45rem;
            margin-top: 0.45rem;
        }
        .model3-price {
            font-size: 3rem;
            font-weight: 700;
            line-height: 1.05;
        }
        .model3-price-unit {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .model3-result-divider {
            height: 1px;
            background: rgba(255, 255, 255, 0.18);
            margin: 1.1rem 0;
        }
        .model3-result-pair-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.9rem;
            margin-bottom: 1rem;
        }
        .model3-mini-value {
            font-size: 1rem;
            font-weight: 700;
            margin-top: 0.15rem;
        }
        .model3-positive {
            color: #7DD3A7;
        }
        .model3-segment-box {
            background: rgba(191, 215, 234, 0.16);
            border: 1px solid rgba(216, 224, 234, 0.18);
            padding: 0.85rem;
            margin-bottom: 1rem;
        }
        .model3-segment-name {
            font-size: 1rem;
            font-weight: 700;
            margin: 0.3rem 0 0.65rem;
        }
        .model3-segment-line,
        .model3-stat-table div {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
        }
        .model3-segment-line {
            font-size: 0.82rem;
            border-top: 1px solid rgba(255, 255, 255, 0.12);
            padding-top: 0.4rem;
            margin-top: 0.4rem;
        }
        .model3-price-position-label {
            margin-top: 0.75rem;
        }
        .model3-chip {
            background: rgba(255, 255, 255, 0.18);
            padding: 0.25rem 0.55rem;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .model3-stat-table {
            background: rgba(0, 0, 0, 0.18);
            padding: 0.75rem;
        }
        .model3-stat-table div {
            font-size: 0.82rem;
            padding: 0.25rem 0;
        }
        .model3-ai-box {
            margin-top: 1rem;
            border: 1px dashed #94A3B8;
            padding: 1rem 1.1rem;
            background: #FFFFFF;
        }
        .model3-ai-title {
            color: #9B1C1C;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .model3-ai-body {
            color: #0F2742;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .model3-segment-desc {
            min-height: 248px;
            padding: 1rem;
            border: 1px solid #D8E0EA;
        }
        .model3-tone-mint {
            background: #E6FFFA;
        }
        .model3-tone-warm {
            background: #FFF4E8;
        }
        .model3-tone-blue {
            background: #EEF4FF;
        }
        .model3-dot-row {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            color: #0F2742;
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }
        .model3-dot {
            width: 0.55rem;
            height: 0.55rem;
            background: #1F7A8C;
            display: inline-block;
        }
        .model3-desc-title {
            color: #0F2742;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .model3-desc-body {
            color: #5B6573;
            font-size: 0.84rem;
            line-height: 1.48;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
