from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data_access import load_pricing_dataset
from components.ui import DEFAULT_PLOTLY_CONFIG, render_metric_grid, two_column_layout


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


def _format_days(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} days"


def _valid_occupancy_days_series(dataframe: pd.DataFrame) -> pd.Series:
    return dataframe["estimated_occupancy_l365d"].where(
        dataframe["estimated_occupancy_l365d"].between(0, 365, inclusive="both")
    )


def _valid_occupancy_rate_series(dataframe: pd.DataFrame) -> pd.Series:
    valid_days = _valid_occupancy_days_series(dataframe)
    return (valid_days / 365.0).where(valid_days.notna())


def _valid_occupancy_listing_mask(dataframe: pd.DataFrame) -> pd.Series:
    return _valid_occupancy_days_series(dataframe).notna()


def _occupancy_coverage_stats(dataframe: pd.DataFrame) -> dict[str, float | int]:
    total_listings = dataframe["listing_id"].nunique()
    valid_occupancy_listings = dataframe.loc[
        _valid_occupancy_listing_mask(dataframe),
        "listing_id",
    ].nunique()
    occupancy_coverage = (
        valid_occupancy_listings / total_listings if total_listings else np.nan
    )
    return {
        "total_listings": total_listings,
        "valid_occupancy_listings": valid_occupancy_listings,
        "occupancy_coverage": occupancy_coverage,
        "median_occupied_days": _valid_occupancy_days_series(dataframe).median(),
    }


def _price_coverage_stats(full_dataframe: pd.DataFrame, priced_dataframe: pd.DataFrame) -> dict[str, float | int]:
    total_listings = full_dataframe["listing_id"].nunique()
    priced_listings = priced_dataframe["listing_id"].nunique()
    price_coverage = priced_listings / total_listings if total_listings else np.nan
    return {
        "total_listings": total_listings,
        "priced_listings": priced_listings,
        "price_coverage": price_coverage,
    }


def _price_slider_bounds(dataframe: pd.DataFrame) -> tuple[float, float, float]:
    positive_prices = dataframe.loc[dataframe["price"] > 0, "price"].dropna()
    if positive_prices.empty:
        return (0.0, 1.0, 1.0)

    min_price = float(positive_prices.min())
    p99_price = float(positive_prices.quantile(0.99))
    if p99_price < min_price:
        p99_price = min_price
    return (min_price, p99_price, p99_price)


def _priced_view(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe[dataframe["price"].notna() & dataframe["price"].gt(0)].copy()


def _render_filters(dataframe: pd.DataFrame) -> dict[str, object]:
    with st.expander("Pricing filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)

        room_type_options = sorted(dataframe["room_type"].dropna().unique().tolist())
        neighbourhood_options = sorted(dataframe["neighbourhood"].dropna().unique().tolist())
        min_price, slider_max_price, default_price_upper = _price_slider_bounds(dataframe)

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
            selected_price_range = st.slider(
                "Listed price range (THB)",
                min_value=float(min_price),
                max_value=float(slider_max_price),
                value=(float(min_price), float(default_price_upper)),
                help=(
                    "The slider maximum is set to the 99th percentile for usability. "
                    "When left at the default maximum, listings priced above P99 remain included."
                ),
                key="pricing_price_range",
            )
        with c4:
            selected_occupancy_days_range = st.slider(
                "Estimated occupied days L365D",
                min_value=0,
                max_value=365,
                value=(0, 365),
                step=1,
                key="pricing_occupancy_days_range",
            )

    return {
        "selected_room_types": selected_room_types,
        "selected_neighbourhoods": selected_neighbourhoods,
        "selected_price_range": selected_price_range,
        "price_slider_default_lower": min_price,
        "price_slider_default_upper": default_price_upper,
        "selected_occupancy_days_range": selected_occupancy_days_range,
    }


def _apply_main_filters(dataframe: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    view = dataframe.copy()
    selected_room_types = filters["selected_room_types"]
    selected_neighbourhoods = filters["selected_neighbourhoods"]
    selected_price_range = filters["selected_price_range"]
    selected_occupancy_days_range = filters["selected_occupancy_days_range"]
    price_slider_default_lower = float(filters["price_slider_default_lower"])
    price_slider_default_upper = float(filters["price_slider_default_upper"])

    if selected_room_types:
        view = view[view["room_type"].isin(selected_room_types)]
    if selected_neighbourhoods:
        view = view[view["neighbourhood"].isin(selected_neighbourhoods)]

    lower_price, upper_price = selected_price_range
    price_filter_changed = (
        not np.isclose(lower_price, price_slider_default_lower)
        or not np.isclose(upper_price, price_slider_default_upper)
    )
    if price_filter_changed:
        price_mask = view["price"].between(lower_price, upper_price, inclusive="both")
        if np.isclose(upper_price, price_slider_default_upper):
            price_mask = price_mask | view["price"].gt(price_slider_default_upper)
        view = view[price_mask]

    occupancy_lower, occupancy_upper = selected_occupancy_days_range
    if (occupancy_lower, occupancy_upper) != (0, 365):
        occupancy_days = _valid_occupancy_days_series(view)
        view = view[
            occupancy_days.notna()
            & occupancy_days.between(occupancy_lower, occupancy_upper, inclusive="both")
        ]

    return view


def _render_kpis(
    dataframe: pd.DataFrame,
    price_coverage_stats: dict[str, float | int],
) -> None:
    review_view = dataframe[
        dataframe["review_scores_rating"].notna() & (dataframe["number_of_reviews"] >= 5)
    ].copy()
    occupancy_stats = _occupancy_coverage_stats(dataframe)
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
                "value": f"{dataframe['listing_id'].nunique():,}",
                "help": "Distinct listings with a valid listed price remaining after global filters.",
            },
            {
                "label": "Median Listed Price",
                "value": _format_thb(dataframe["price"].median()),
                "help": "Primary listed price KPI based on listing_snapshot_price. Median is more stable than average when outliers exist.",
            },
            {
                "label": "Typical Price Range",
                "value": (
                    f"{_format_thb_number(dataframe['price'].quantile(0.25))}"
                    f"-{_format_thb_number(dataframe['price'].quantile(0.75))} THB"
                ),
                "help": "Typical listed price band for the bulk of listings after global filters.",
            },
            {
                "label": "Median Est. Occupied Days L365D",
                "value": _format_days(occupancy_stats["median_occupied_days"]),
                "help": "Median source-derived occupied-day estimate across distinct listings with valid estimates only.",
            },
            {
                "label": "Avg Est. Revenue / Listing L365D",
                "value": _format_thb(revenue_per_listing),
                "help": "Average source-derived estimated revenue among listings with non-null estimated revenue.",
            },
            {
                "label": "Median Review Score",
                "value": _format_score(review_view["review_scores_rating"].median()),
                "help": "Only uses listings with a non-null review score and at least 5 reviews.",
            },
        ],
        cards_per_row=3,
    )
    st.caption(
        "Source-derived estimates only · "
        f"Overall price coverage: {price_coverage_stats['priced_listings']:,}/"
        f"{price_coverage_stats['total_listings']:,} "
        f"({_format_pct(price_coverage_stats['price_coverage'])}) · "
        f"Occupancy estimate coverage: "
        f"{occupancy_stats['valid_occupancy_listings']:,}/"
        f"{occupancy_stats['total_listings']:,} "
        f"({_format_pct(occupancy_stats['occupancy_coverage'])})."
    )


def _build_price_distribution(dataframe: pd.DataFrame) -> go.Figure:
    priced = _priced_view(dataframe)
    if priced.empty:
        return go.Figure()
    p99 = priced["price"].quantile(0.99)
    view = priced[priced["price"] <= p99].copy()
    median_price = priced["price"].median()
    p75_price = priced["price"].quantile(0.75)

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
    view = _priced_view(dataframe)
    if view.empty:
        return go.Figure()
    summary = (
        view.groupby("room_type", dropna=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "median_price": frame["price"].median(),
                    "p25_price": frame["price"].quantile(0.25),
                    "p75_price": frame["price"].quantile(0.75),
                    "listing_count": frame["listing_id"].nunique(),
                }
            )
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
                "Listing count: %{customdata[2]:,.0f}<extra></extra>"
            ),
            name="Median price",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary["room_type"],
            y=summary["median_price"],
            mode="markers",
            marker=dict(color="#1F7A8C", size=1),
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
    view = _priced_view(dataframe)
    if view.empty:
        return go.Figure()
    neighbourhood_summary = (
        view.groupby("neighbourhood", dropna=False)
        .agg(
            total_listing_count=("listing_id", "nunique"),
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
        top_neighbourhoods.sort_values("overall_median_price", ascending=False)["neighbourhood"].tolist()
    )

    summary = (
        view.groupby(["neighbourhood", "room_type"], dropna=False)
        .agg(
            median_price=("price", "median"),
            listing_count=("listing_id", "nunique"),
        )
        .reset_index()
    )
    summary = summary[summary["neighbourhood"].isin(ordered_neighbourhoods)]
    summary["median_price"] = summary["median_price"].where(summary["listing_count"] >= 10)
    if summary["median_price"].notna().sum() == 0:
        return go.Figure()

    room_type_order = (
        view.groupby("room_type", dropna=False)["price"]
        .median()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    pivot = summary.pivot(index="neighbourhood", columns="room_type", values="median_price")
    pivot = pivot.reindex(index=ordered_neighbourhoods, columns=room_type_order)
    counts = summary.pivot(index="neighbourhood", columns="room_type", values="listing_count")
    counts = counts.reindex(index=ordered_neighbourhoods, columns=room_type_order)

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
            customdata=np.dstack([counts.values]),
            hovertemplate=(
                "Neighbourhood: %{y}<br>"
                "Room type: %{x}<br>"
                "Median listed price: %{z:,.0f} THB<br>"
                "Valid listings: %{customdata[0]:,.0f}<extra></extra>"
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
        margin=dict(l=0, r=16, t=52, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _build_price_vs_performance(dataframe: pd.DataFrame) -> go.Figure:
    view = _priced_view(dataframe)
    view = view[_valid_occupancy_listing_mask(view)].copy()
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
            median_occupied_days=("estimated_occupancy_l365d", "median"),
            listing_count=("listing_id", "nunique"),
            median_price=("price", "median"),
            median_estimated_revenue=("estimated_revenue_l365d", "median"),
        )
        .reset_index()
    )
    summary = summary[summary["listing_count"] >= 10].copy()
    summary["price_range"] = pd.Categorical(summary["price_range"], categories=price_labels, ordered=True)
    summary = summary.sort_values("price_range")
    if summary.empty:
        return go.Figure()

    fig = px.bar(
        summary,
        x="price_range",
        y="median_occupied_days",
        labels={
            "price_range": "Listed Price Range",
            "median_occupied_days": "Median Est. Occupied Days L365D",
        },
        title="Median Est. Occupied Days by Price Range",
        text_auto=".0f",
    )
    fig.update_traces(
        marker_color="#0F2742",
        customdata=np.column_stack(
            [
                summary["listing_count"],
                summary["median_price"],
                summary["median_estimated_revenue"],
            ]
        ),
        hovertemplate=(
            "Listed price range: %{x}<br>"
            "Median estimated occupied days L365D: %{y:,.0f} days<br>"
            "Listing count: %{customdata[0]:,.0f}<br>"
            "Median listed price: %{customdata[1]:,.0f} THB<br>"
            "Median est. revenue: %{customdata[2]:,.0f} THB<extra></extra>"
        ),
        texttemplate="%{y:,.0f} days",
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        title_font=dict(size=18, color="#0F2742"),
        yaxis_title="Median Est. Occupied Days L365D",
    )
    return fig


def _prepare_quadrant_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    view = dataframe[_valid_occupancy_listing_mask(dataframe)].copy()
    if view.empty:
        return view

    view["price_percentile_by_room_type"] = (
        view.groupby("room_type")["price"].rank(pct=True, method="average").fillna(0)
    )
    view["occupancy_percentile"] = _valid_occupancy_rate_series(view).rank(
        pct=True,
        method="average",
    ).fillna(0)

    conditions = [
        (view["price_percentile_by_room_type"] >= 0.75) & (view["occupancy_percentile"] >= 0.5),
        (view["price_percentile_by_room_type"] >= 0.75) & (view["occupancy_percentile"] < 0.5),
        (view["price_percentile_by_room_type"] < 0.75) & (view["occupancy_percentile"] >= 0.5),
    ]
    labels = [
        "Premium High-Perform",
        "Premium Underperform",
        "Budget High-Perform",
    ]
    view["quadrant_group"] = np.select(conditions, labels, default="Underperform")
    return view


def _style_watchlist(dataframe: pd.DataFrame) -> pd.io.formats.style.Styler:
    occupancy_values = dataframe["Est. Occupied Days L365D"].dropna()
    high_days_threshold = occupancy_values.quantile(0.75) if not occupancy_values.empty else np.nan
    low_days_threshold = occupancy_values.quantile(0.25) if not occupancy_values.empty else np.nan

    def occupancy_style(value: float) -> str:
        if pd.isna(value):
            return ""
        if pd.notna(high_days_threshold) and value >= high_days_threshold:
            return "background-color: #E6FFFA; color: #0F5132;"
        if pd.notna(low_days_threshold) and value <= low_days_threshold:
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
            "Est. Occupied Days L365D": "{:,.0f} days",
            "Est. Revenue L365D": "{:,.0f} THB",
            "Review Score": "{:.2f}",
            "Reviews": "{:,.0f}",
            "Price / Person": "{:,.0f} THB",
        },
        na_rep="N/A",
    )
    styler = styler.map(occupancy_style, subset=["Est. Occupied Days L365D"])
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
        "estimated_occupancy_l365d",
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
        & _valid_occupancy_listing_mask(view)
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
            "estimated_occupancy_l365d": "Est. Occupied Days L365D",
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
            "Est. Occupied Days L365D",
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
        if high_price_within_room_type and row["number_of_reviews"] < low_review_count_threshold:
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
            "estimated_occupancy_l365d",
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
            "estimated_occupancy_l365d": "Est. Occupied Days L365D",
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
            "Est. Occupied Days L365D",
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
    ).where(
        pricing["estimated_occupancy_l365d"].between(0, 365, inclusive="both")
    ).clip(lower=0, upper=1)

    priced_pricing = _priced_view(pricing)
    if priced_pricing.empty:
        st.warning("No listings with valid listed prices are available for pricing analysis.")
        return

    price_coverage_stats = _price_coverage_stats(pricing, priced_pricing)

    filters = _render_filters(priced_pricing)
    main_filtered = _apply_main_filters(priced_pricing, filters)
    if main_filtered.empty:
        st.warning("No listings match the current filter set.")
        return

    _render_kpis(main_filtered, price_coverage_stats)

    p99_price = main_filtered["price"].quantile(0.99) if not main_filtered.empty else np.nan

    row_1_left, row_1_right = two_column_layout([1.15, 0.85])
    with row_1_left:
        st.plotly_chart(
            _build_price_distribution(main_filtered),
            use_container_width=True,
            config=DEFAULT_PLOTLY_CONFIG,
        )
        st.caption(
            "Display capped at P99; median and P75 use the full filtered data."
        )
    with row_1_right:
        st.plotly_chart(
            _build_price_by_segment(main_filtered),
            use_container_width=True,
            config=DEFAULT_PLOTLY_CONFIG,
        )

    row_2_left, row_2_right = two_column_layout([1.0, 1.2])
    with row_2_left:
        matrix = _build_pricing_strategy_matrix(main_filtered)
        if matrix.data:
            st.plotly_chart(matrix, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
            st.caption(
                "Top 10 neighbourhoods; cells with fewer than 10 priced listings are hidden."
            )
        else:
            st.info("Not enough dense neighbourhood x room type combinations to render the pricing matrix.")
    with row_2_right:
        perf = _build_price_vs_performance(main_filtered)
        if perf.data:
            st.plotly_chart(perf, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("Not enough listings with valid occupancy data to render the price-range performance view.")

    st.markdown("#### Listing Benchmark & Watchlist")
    top_tab, watchlist_tab = st.tabs(["Top Performers", "Watchlist"])

    with top_tab:
        st.caption("Top 1% listed-price outliers are excluded.")
        top_performers = _build_top_performers(main_filtered, p99_price)
        if top_performers.empty:
            st.info("No listings qualify for Top Performers under the current filters.")
        else:
            st.dataframe(
                _style_watchlist(top_performers),
                use_container_width=True,
                hide_index=True,
            )
    with watchlist_tab:
        watchlist = _build_watchlist(main_filtered, p99_price)
        if watchlist.empty:
            st.info("No premium underperformers or top 1% price listings under the current filters.")
        else:
            st.dataframe(
                _style_watchlist(watchlist),
                use_container_width=True,
                hide_index=True,
            )
