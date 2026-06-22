from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data_access import load_pricing_dataset
from components.ui import render_metric_grid, two_column_layout


def _format_thb(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} THB"


def _format_thb_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"


def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1%}"


def _format_score(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}"


def _render_filters(dataframe: pd.DataFrame) -> dict[str, object]:
    with st.expander("Pricing filters", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)

        room_type_options = sorted(dataframe["room_type"].dropna().unique().tolist())
        neighbourhood_options = sorted(dataframe["neighbourhood"].dropna().unique().tolist())
        property_type_options = sorted(dataframe["property_type"].dropna().unique().tolist())

        with c1:
            selected_room_types = st.multiselect(
                "Room type",
                options=room_type_options,
                default=[],
                key="pricing_room_types",
            )
        with c2:
            selected_neighbourhoods = st.multiselect(
                "Neighbourhood",
                options=neighbourhood_options,
                default=[],
                key="pricing_neighbourhoods",
            )
        with c3:
            min_price = float(dataframe["price"].min())
            max_price = float(dataframe["price"].max())
            selected_price_range = st.slider(
                "Listed Price Range (THB)",
                min_value=float(min_price),
                max_value=float(max_price),
                value=(float(min_price), float(max_price)),
                key="pricing_price_range",
            )
        with c4:
            occupancy_max = float(
                dataframe["estimated_occupancy_rate_l365d"].fillna(0).max()
            )
            selected_occupancy_range = st.slider(
                "Estimated occupancy rate",
                min_value=0.0,
                max_value=max(1.0, occupancy_max),
                value=(0.0, max(1.0, occupancy_max)),
                step=0.05,
                format="%.2f",
                key="pricing_occupancy_range",
            )
        with c5:
            reviewed_only = st.toggle(
                "Review reliability",
                value=False,
                help="Only keep listings with at least 5 reviews.",
                key="pricing_review_reliability",
            )

        with st.container():
            a1, a2, a3 = st.columns(3)
            with a1:
                selected_property_types = st.multiselect(
                    "Property type",
                    options=property_type_options,
                    default=[],
                    key="pricing_property_types",
                )
            with a2:
                search_text = st.text_input(
                    "Listing / host search",
                    value="",
                    key="pricing_search_text",
                )
            with a3:
                st.caption(
                    "Estimated occupancy and revenue come from source-derived fields, not confirmed booking transactions."
                )

    return {
        "selected_room_types": selected_room_types,
        "selected_neighbourhoods": selected_neighbourhoods,
        "selected_price_range": selected_price_range,
        "selected_occupancy_range": selected_occupancy_range,
        "reviewed_only": reviewed_only,
        "selected_property_types": selected_property_types,
        "search_text": search_text,
    }


def _apply_filters(
    dataframe: pd.DataFrame,
    filters: dict[str, object],
    *,
    apply_price_range: bool = True,
    apply_review_reliability: bool = True,
) -> pd.DataFrame:
    view = dataframe.copy()
    selected_room_types = filters["selected_room_types"]
    selected_neighbourhoods = filters["selected_neighbourhoods"]
    selected_price_range = filters["selected_price_range"]
    selected_occupancy_range = filters["selected_occupancy_range"]
    reviewed_only = filters["reviewed_only"]
    selected_property_types = filters["selected_property_types"]
    search_text = str(filters["search_text"])

    if selected_room_types:
        view = view[view["room_type"].isin(selected_room_types)]
    if selected_neighbourhoods:
        view = view[view["neighbourhood"].isin(selected_neighbourhoods)]
    if selected_property_types:
        view = view[view["property_type"].isin(selected_property_types)]
    if apply_price_range:
        view = view[
            view["price"].between(selected_price_range[0], selected_price_range[1], inclusive="both")
        ]
    view = view[
        view["estimated_occupancy_rate_l365d"].fillna(0).between(
            selected_occupancy_range[0],
            selected_occupancy_range[1],
            inclusive="both",
        )
    ]
    if reviewed_only and apply_review_reliability:
        view = view[view["number_of_reviews"] >= 5]
    if search_text.strip():
        pattern = search_text.strip().lower()
        view = view[
            view["listing_name"].str.lower().str.contains(pattern, na=False)
            | view["host_name"].str.lower().str.contains(pattern, na=False)
            | view["listing_id"].astype(str).str.contains(pattern, na=False)
        ]
    return view


def _render_kpis(dataframe: pd.DataFrame) -> None:
    review_view = dataframe[
        dataframe["review_scores_rating"].notna() & (dataframe["number_of_reviews"] >= 5)
    ].copy()
    revenue_eligible = dataframe[dataframe["estimated_revenue_l365d"].notna()].copy()
    revenue_per_listing = (
        revenue_eligible["estimated_revenue_l365d"].sum() / len(revenue_eligible)
        if not revenue_eligible.empty
        else np.nan
    )

    render_metric_grid(
        [
            {
                "label": "Valid Listings",
                "value": f"{len(dataframe[dataframe['price'] > 0]):,}",
                "help": "Number of listings remaining after filters with positive listed price.",
            },
            {
                "label": "Median Listed Price",
                "value": _format_thb(dataframe["price"].median()),
                "help": "Primary listed price KPI based on listing_snapshot_price. Median is more stable than average when outliers exist.",
            },
            {
                "label": "Typical Price Range",
                "value": (
                    f"{_format_thb_number(dataframe['price'].quantile(0.25))} - "
                    f"{_format_thb_number(dataframe['price'].quantile(0.75))} THB"
                ),
                "help": "Typical listed price band for the bulk of listings after filters.",
            },
            {
                "label": "Median Est. Occupancy Rate L365D",
                "value": _format_pct(dataframe["estimated_occupancy_rate_l365d"].median()),
                "help": "Median source-derived estimated occupancy rate, calculated from estimated occupied days over the trailing 365-day window.",
            },
            {
                "label": "Avg Est. Revenue / Listing L365D",
                "value": _format_thb(revenue_per_listing),
                "help": "Average source-derived estimated revenue among listings with non-null estimated revenue.",
            },
            {
                "label": "Median Review Score",
                "value": _format_score(review_view["review_scores_rating"].median()),
                "help": "Only uses listings with at least 5 reviews.",
            },
        ],
        cards_per_row=3,
    )
    st.caption(
        "Estimated Revenue and Estimated Occupancy are source-derived estimated indicators for relative comparison, not confirmed transaction-based booking results."
    )


def _build_price_distribution(dataframe: pd.DataFrame) -> go.Figure:
    p99 = dataframe["price"].quantile(0.99)
    view = dataframe[dataframe["price"] <= p99].copy()
    median_price = dataframe["price"].median()
    p75_price = dataframe["price"].quantile(0.75)

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=view["price"],
            nbinsx=40,
            marker_color="#0F2742",
            opacity=0.9,
            hovertemplate="Price bucket: %{x:,.0f} THB<br>Listings: %{y}<extra></extra>",
        )
    )
    fig.add_vline(
        x=median_price,
        line_dash="dash",
        line_color="#1F7A8C",
        annotation_text="Median",
        annotation_position="top left",
    )
    fig.add_vline(
        x=p75_price,
        line_dash="dot",
        line_color="#BF6C32",
        annotation_text="P75",
        annotation_position="top right",
    )
    fig.update_layout(
        title="Listed Price Distribution",
        title_font=dict(size=18, color="#0F2742"),
        xaxis_title="Listed Price (THB)",
        yaxis_title="Listing count",
        height=340,
        margin=dict(l=0, r=0, t=56, b=0),
        bargap=0.05,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _build_price_by_segment(dataframe: pd.DataFrame) -> go.Figure:
    summary = (
        dataframe.groupby("room_type", dropna=False)
        .agg(
            median_price=("price", "median"),
            p25_price=("price", lambda values: values.quantile(0.25)),
            p75_price=("price", lambda values: values.quantile(0.75)),
            listing_count=("listing_id", "count"),
        )
        .reset_index()
        .sort_values("median_price", ascending=False)
    )
    if summary.empty:
        return go.Figure()

    summary["iqr_width"] = summary["p75_price"] - summary["p25_price"]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=summary["room_type"],
            y=summary["median_price"],
            marker_color="#0F2742",
            customdata=np.column_stack(
                [
                    summary["p25_price"],
                    summary["p75_price"],
                    summary["listing_count"],
                ]
            ),
            hovertemplate=(
                "Room type: %{x}<br>"
                "Median listed price: %{y:,.0f} THB<br>"
                "P25: %{customdata[0]:,.0f} THB<br>"
                "P75: %{customdata[1]:,.0f} THB<br>"
                "Listings: %{customdata[2]:,.0f}<extra></extra>"
            ),
            name="Median price",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary["room_type"],
            y=summary["median_price"],
            mode="markers",
            marker=dict(
                color="#1F7A8C",
                size=1,
            ),
            error_y=dict(
                type="data",
                symmetric=False,
                array=(summary["p75_price"] - summary["median_price"]).clip(lower=0),
                arrayminus=(summary["median_price"] - summary["p25_price"]).clip(lower=0),
                color="#BF6C32",
                thickness=2.5,
                width=10,
            ),
            customdata=np.column_stack(
                [
                    summary["p25_price"],
                    summary["p75_price"],
                    summary["iqr_width"],
                ]
            ),
            hovertemplate=(
                "Room type: %{x}<br>"
                "Median listed price: %{y:,.0f} THB<br>"
                "P25-P75 range: %{customdata[0]:,.0f} - %{customdata[1]:,.0f} THB<br>"
                "IQR width: %{customdata[2]:,.0f} THB<extra></extra>"
            ),
            name="P25-P75 range",
            showlegend=False,
        )
    )
    fig.update_layout(
        title="Price Spread by Room Type",
        title_font=dict(size=18, color="#0F2742"),
        xaxis_title="Room type",
        yaxis_title="Listed Price (THB)",
        height=340,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _build_pricing_strategy_matrix(dataframe: pd.DataFrame) -> go.Figure:
    neighbourhood_summary = (
        dataframe.groupby("neighbourhood", dropna=False)
        .agg(
            total_listing_count=("listing_id", "count"),
            overall_median_price=("price", "median"),
        )
        .reset_index()
    )
    top_neighbourhoods = (
        neighbourhood_summary.sort_values(
            ["total_listing_count", "overall_median_price"],
            ascending=[False, False],
        )
        .head(10)
        .copy()
    )
    ordered_neighbourhoods = (
        top_neighbourhoods.sort_values("overall_median_price", ascending=False)[
            "neighbourhood"
        ].tolist()
    )

    summary = (
        dataframe.groupby(["neighbourhood", "room_type"], dropna=False)
        .agg(
            median_price=("price", "median"),
            listing_count=("listing_id", "count"),
        )
        .reset_index()
    )
    summary = summary[summary["neighbourhood"].isin(ordered_neighbourhoods)]
    summary["median_price"] = summary["median_price"].where(summary["listing_count"] >= 10)
    if summary["median_price"].notna().sum() == 0:
        return go.Figure()

    room_type_order = (
        dataframe.groupby("room_type", dropna=False)["price"]
        .median()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    pivot = summary.pivot(
        index="neighbourhood",
        columns="room_type",
        values="median_price",
    )
    pivot = pivot.reindex(index=ordered_neighbourhoods, columns=room_type_order)
    counts = summary.pivot(
        index="neighbourhood",
        columns="room_type",
        values="listing_count",
    ).reindex(index=ordered_neighbourhoods, columns=room_type_order)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=[
                [0.0, "#FFF4E8"],
                [0.25, "#F3D1AE"],
                [0.5, "#E5A86C"],
                [0.75, "#BF6C32"],
                [1.0, "#7A3B12"],
            ],
            customdata=counts.values,
            hovertemplate=(
                "Neighbourhood: %{y}<br>"
                "Room type: %{x}<br>"
                "Median listed price: %{z:,.0f} THB<br>"
                "Listings: %{customdata:,.0f}<extra></extra>"
            ),
            colorbar=dict(title="Median Listed Price (THB)"),
        )
    )
    fig.update_layout(
        title="Neighbourhood Price Matrix",
        title_font=dict(size=18, color="#0F2742"),
        xaxis_title="Room type",
        yaxis_title="Neighbourhood",
        height=420,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _build_price_vs_performance(dataframe: pd.DataFrame) -> go.Figure:
    view = dataframe[dataframe["estimated_occupancy_rate_l365d"].notna()].copy()
    if view.empty:
        return go.Figure()
    price_bins = [0, 750, 1100, 1500, 2000, 3000, np.inf]
    price_labels = [
        "< 750 THB",
        "750 - 1,099 THB",
        "1,100 - 1,499 THB",
        "1,500 - 1,999 THB",
        "2,000 - 2,999 THB",
        "3,000+ THB",
    ]
    view["price_range"] = pd.cut(
        view["price"],
        bins=price_bins,
        labels=price_labels,
        right=False,
        include_lowest=True,
    )
    summary = (
        view.groupby("price_range", observed=False)
        .agg(
            median_occupancy_rate=("estimated_occupancy_rate_l365d", "median"),
            median_occupied_days=("estimated_occupancy_l365d", "median"),
            listing_count=("listing_id", "count"),
            median_price=("price", "median"),
            median_estimated_revenue=("estimated_revenue_l365d", "median"),
        )
        .reset_index()
    )
    summary = summary[summary["listing_count"] >= 10].copy()
    summary["price_range"] = pd.Categorical(
        summary["price_range"],
        categories=price_labels,
        ordered=True,
    )
    summary = summary.sort_values("price_range")
    if summary.empty:
        return go.Figure()

    fig = px.bar(
        summary,
        x="price_range",
        y="median_occupancy_rate",
        labels={
            "price_range": "Listed Price Range",
            "median_occupancy_rate": "Median Source-Estimated Occupancy Rate L365D",
        },
        title="Median Est. Occupancy Rate by Price Range",
        text_auto=".1%",
    )
    fig.update_traces(
        marker_color="#0F2742",
        customdata=np.column_stack(
            [
                summary["listing_count"],
                summary["median_price"],
                summary["median_estimated_revenue"],
                summary["median_occupied_days"],
            ]
        ),
        hovertemplate=(
            "Listed price range: %{x}<br>"
            "Median source-est. occupancy rate: %{y:.1%}<br>"
            "Median est. occupied days L365D: %{customdata[3]:,.0f}<br>"
            "Listing count: %{customdata[0]:,.0f}<br>"
            "Median listed price: %{customdata[1]:,.0f} THB<br>"
            "Median est. revenue: %{customdata[2]:,.0f} THB<extra></extra>"
        ),
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        yaxis_tickformat=".0%",
        title_font=dict(size=18, color="#0F2742"),
    )
    return fig


def _prepare_quadrant_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    view = dataframe[dataframe["estimated_occupancy_rate_l365d"].notna()].copy()
    if view.empty:
        return view

    view["price_percentile_by_room_type"] = (
        view.groupby("room_type")["price"]
        .rank(pct=True, method="average")
        .fillna(0)
    )
    view["occupancy_percentile"] = view["estimated_occupancy_rate_l365d"].rank(
        pct=True,
        method="average",
    ).fillna(0)

    conditions = [
        (view["price_percentile_by_room_type"] >= 0.75)
        & (view["occupancy_percentile"] >= 0.5),
        (view["price_percentile_by_room_type"] >= 0.75)
        & (view["occupancy_percentile"] < 0.5),
        (view["price_percentile_by_room_type"] < 0.75)
        & (view["occupancy_percentile"] >= 0.5),
    ]
    labels = [
        "Premium High-Perform",
        "Premium Underperform",
        "Budget High-Perform",
    ]
    view["quadrant_group"] = np.select(conditions, labels, default="Underperform")
    return view


def _style_watchlist(dataframe: pd.DataFrame) -> pd.io.formats.style.Styler:
    def occupancy_style(value: float) -> str:
        if pd.isna(value):
            return ""
        if value >= 0.7:
            return "background-color: #E6FFFA; color: #0F5132;"
        if value < 0.4:
            return "background-color: #FFF1F2; color: #9B1C1C;"
        return ""

    def review_style(value: float) -> str:
        if pd.isna(value):
            return ""
        if value >= 4.8:
            return "background-color: #E6FFFA; color: #0F5132;"
        if value < 4.3:
            return "background-color: #FFF1F2; color: #9B1C1C;"
        if value < 4.8:
            return "background-color: #FFFBEB; color: #92400E;"
        return ""

    styler = dataframe.style.format(
        {
            "Listed Price": "{:,.0f} THB",
            "Est. Occupancy Rate L365D": "{:.1%}",
            "Est. Revenue L365D": "{:,.0f} THB",
            "Review Score": "{:.2f}",
            "Reviews": "{:,.0f}",
            "Price / Person": "{:,.0f} THB",
        }
    )
    styler = styler.map(occupancy_style, subset=["Est. Occupancy Rate L365D"])
    styler = styler.map(review_style, subset=["Review Score"])
    return styler


def _build_top_performers(
    dataframe: pd.DataFrame,
    top_price_threshold: float | None,
) -> pd.DataFrame:
    cols = [
        "listing_id",
        "listing_name",
        "host_name",
        "room_type",
        "neighbourhood",
        "price",
        "estimated_occupancy_rate_l365d",
        "estimated_revenue_l365d",
        "review_scores_rating",
        "number_of_reviews",
        "price_per_person",
    ]
    view = dataframe.loc[:, cols].copy()
    view = view[
        (view["price"] > 0)
        & view["estimated_revenue_l365d"].notna()
        & view["estimated_occupancy_rate_l365d"].notna()
    ].copy()
    if top_price_threshold is not None and not pd.isna(top_price_threshold):
        view = view[view["price"] < top_price_threshold].copy()
    view = view.sort_values(
        ["estimated_revenue_l365d", "estimated_occupancy_rate_l365d", "price"],
        ascending=[False, False, False],
    ).head(20)
    return view.rename(
        columns={
            "listing_id": "Listing ID",
            "listing_name": "Listing",
            "host_name": "Host",
            "room_type": "Room Type",
            "neighbourhood": "Neighbourhood",
            "price": "Listed Price",
            "estimated_occupancy_rate_l365d": "Est. Occupancy Rate L365D",
            "estimated_revenue_l365d": "Est. Revenue L365D",
            "review_scores_rating": "Review Score",
            "number_of_reviews": "Reviews",
            "price_per_person": "Price / Person",
        }
    )[
        [
            "Listing ID",
            "Listing",
            "Neighbourhood",
            "Room Type",
            "Listed Price",
            "Est. Occupancy Rate L365D",
            "Est. Revenue L365D",
            "Review Score",
            "Reviews",
            "Price / Person",
            "Host",
        ]
    ]


def _build_watchlist(
    dataframe: pd.DataFrame,
    top_price_threshold: float | None,
) -> pd.DataFrame:
    view = _prepare_quadrant_data(dataframe)
    if view.empty:
        return pd.DataFrame()

    low_review_score_threshold = 4.5
    low_review_count_threshold = 5

    def build_watchlist_reason(row: pd.Series) -> str:
        reasons: list[str] = []
        high_price_within_room_type = row["price_percentile_by_room_type"] >= 0.75
        if high_price_within_room_type and row["occupancy_percentile"] < 0.5:
            reasons.append("Premium Underperform")
        if top_price_threshold is not None and not pd.isna(top_price_threshold) and row["price"] >= top_price_threshold:
            reasons.append("Top 1% Price")
        if (
            high_price_within_room_type
            and pd.notna(row["review_scores_rating"])
            and row["review_scores_rating"] < low_review_score_threshold
            and row["number_of_reviews"] >= low_review_count_threshold
        ):
            reasons.append("High Price + Low Review")
        if (
            high_price_within_room_type
            and row["number_of_reviews"] < low_review_count_threshold
        ):
            reasons.append("High Price + Low Review Count")
        return "; ".join(reasons)

    view["watchlist_reason"] = view.apply(build_watchlist_reason, axis=1)
    watchlist = view[view["watchlist_reason"] != ""].copy()
    watchlist = watchlist.sort_values(
        ["price_percentile_by_room_type", "occupancy_percentile", "estimated_revenue_l365d"],
        ascending=[False, True, False],
    ).head(20)
    return watchlist.loc[
        :,
        [
            "listing_id",
            "listing_name",
            "host_name",
            "room_type",
            "neighbourhood",
            "price",
            "estimated_occupancy_rate_l365d",
            "estimated_revenue_l365d",
            "review_scores_rating",
            "number_of_reviews",
            "price_per_person",
            "watchlist_reason",
        ],
    ].rename(
        columns={
            "listing_id": "Listing ID",
            "listing_name": "Listing",
            "host_name": "Host",
            "room_type": "Room Type",
            "neighbourhood": "Neighbourhood",
            "price": "Listed Price",
            "estimated_occupancy_rate_l365d": "Est. Occupancy Rate L365D",
            "estimated_revenue_l365d": "Est. Revenue L365D",
            "review_scores_rating": "Review Score",
            "number_of_reviews": "Reviews",
            "price_per_person": "Price / Person",
            "watchlist_reason": "Watchlist Reason",
        }
    )[
        [
            "Listing ID",
            "Listing",
            "Watchlist Reason",
            "Neighbourhood",
            "Room Type",
            "Listed Price",
            "Est. Occupancy Rate L365D",
            "Est. Revenue L365D",
            "Review Score",
            "Reviews",
            "Price / Person",
            "Host",
        ]
    ]


def render_pricing_listing_performance() -> None:
    try:
        pricing = load_pricing_dataset()
    except Exception as exc:  # pragma: no cover
        st.error(f"Cannot load pricing dataset from Gold layer.\n\nError: {exc}")
        return

    if pricing.empty:
        st.warning("Pricing dataset is empty.")
        return

    pricing = pricing.copy()
    pricing["estimated_occupancy_rate_l365d"] = (
        pricing["estimated_occupancy_l365d"] / 365.0
    )

    filters = _render_filters(pricing)
    filtered = _apply_filters(
        pricing,
        filters,
        apply_price_range=True,
        apply_review_reliability=False,
    )
    filtered_review = _apply_filters(
        pricing,
        filters,
        apply_price_range=True,
        apply_review_reliability=True,
    )
    filtered_review_no_price_range = _apply_filters(
        pricing,
        filters,
        apply_price_range=False,
        apply_review_reliability=True,
    )
    filtered_no_price_range = _apply_filters(
        pricing,
        filters,
        apply_price_range=False,
        apply_review_reliability=False,
    )
    if filtered.empty:
        st.warning("No listings match the current filter set.")
        return

    top_price_threshold = (
        filtered_review_no_price_range.loc[
            filtered_review_no_price_range["price"] > 0,
            "price",
        ].quantile(0.99)
        if not filtered_review_no_price_range.empty
        else np.nan
    )

    _render_kpis(filtered_review)

    row_1_left, row_1_right = two_column_layout([1.15, 0.85])
    with row_1_left:
        st.plotly_chart(_build_price_distribution(filtered), use_container_width=True)
        st.caption(
            "Prices are capped at P99 for display readability only. Median and P75 are calculated from the full filtered dataset."
        )
    with row_1_right:
        st.plotly_chart(_build_price_by_segment(filtered), use_container_width=True)

    row_2_left, row_2_right = two_column_layout([1.0, 1.2])
    with row_2_left:
        matrix = _build_pricing_strategy_matrix(filtered)
        if matrix.data:
            st.plotly_chart(matrix, use_container_width=True)
            st.caption(
                "Heatmap focuses on the 10 largest neighbourhoods by listing count. Cells with fewer than 10 listings are hidden to avoid unstable median values."
            )
        else:
            st.info("Not enough dense neighbourhood x room type combinations to render the pricing matrix.")
    with row_2_right:
        perf = _build_price_vs_performance(filtered_no_price_range)
        if perf.data:
            st.plotly_chart(perf, use_container_width=True)
            st.caption(
                "This listed-price-range view ignores the Listed Price Range slicer to keep buckets comparable. Estimated occupancy is source-derived and used for relative comparison, not transaction-based booking occupancy."
            )
        else:
            st.info("Not enough listings with valid occupancy data to render the price-range performance view.")

    st.markdown("#### Listing Benchmark & Watchlist")
    st.caption(
        "Est. Occupancy Rate and Est. Revenue are source-derived estimated indicators used for relative comparison and drill-down analysis. They do not represent confirmed transaction-based booking results."
    )
    top_tab, watchlist_tab = st.tabs(["Top Performers", "Watchlist"])

    with top_tab:
        st.dataframe(
            _style_watchlist(_build_top_performers(filtered_review, top_price_threshold)),
            use_container_width=True,
            hide_index=True,
        )
    with watchlist_tab:
        watchlist = _build_watchlist(filtered_review, top_price_threshold)
        if watchlist.empty:
            st.info("No premium underperformers or top 1% price listings under the current filters.")
        else:
            st.dataframe(
                _style_watchlist(watchlist),
                use_container_width=True,
                hide_index=True,
            )
    st.caption("Use this table for listing-level drill-down after reviewing the summary charts.")
