from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data_access import load_overview_dataset
from components.ui import DEFAULT_PLOTLY_CONFIG, render_metric_grid, two_column_layout


REQUIRED_COLUMNS = {
    "listing_id",
    "host_id",
    "neighbourhood",
    "room_type",
    "price",
    "latitude",
    "longitude",
    "estimated_occupancy_l365d",
    "estimated_revenue_l365d",
    "estimated_occupancy_rate_l365d",
    "number_of_reviews",
    "review_scores_rating",
    "is_reliable_review",
}


def _format_thb(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} THB"


def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1%}"


def _format_days(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if float(value).is_integer():
        return f"{int(value)} days"
    return f"{value:.1f} days"


def _valid_occupancy_listing_mask(dataframe: pd.DataFrame) -> pd.Series:
    return dataframe["estimated_occupancy_l365d"].between(0, 365, inclusive="both")


def _occupancy_coverage_stats(dataframe: pd.DataFrame) -> dict[str, float | int]:
    total_listings = dataframe["listing_id"].nunique()
    valid_occupancy_listings = dataframe.loc[
        _valid_occupancy_listing_mask(dataframe),
        "listing_id",
    ].nunique()
    occupancy_coverage = (
        valid_occupancy_listings / total_listings if total_listings else pd.NA
    )
    return {
        "total_listings": total_listings,
        "valid_occupancy_listings": valid_occupancy_listings,
        "occupancy_coverage": occupancy_coverage,
        "median_occupancy_days": dataframe.loc[
            _valid_occupancy_listing_mask(dataframe),
            "estimated_occupancy_l365d",
        ].median(),
    }


def _price_coverage_stats(dataframe: pd.DataFrame) -> dict[str, float | int]:
    total_listings = dataframe["listing_id"].nunique()
    valid_price_listings = dataframe.loc[dataframe["price"] > 0, "listing_id"].nunique()
    price_coverage = valid_price_listings / total_listings if total_listings else pd.NA
    return {
        "total_listings": total_listings,
        "valid_price_listings": valid_price_listings,
        "price_coverage": price_coverage,
        "median_price": dataframe.loc[dataframe["price"] > 0, "price"].median(),
    }


def _valid_coordinate_mask(dataframe: pd.DataFrame) -> pd.Series:
    return (
        dataframe["latitude"].notna()
        & dataframe["longitude"].notna()
        & dataframe["latitude"].between(-90, 90, inclusive="both")
        & dataframe["longitude"].between(-180, 180, inclusive="both")
    )


def _coordinate_coverage_stats(dataframe: pd.DataFrame) -> dict[str, float | int]:
    total_listings = dataframe["listing_id"].nunique()
    valid_coordinate_listings = dataframe.loc[
        _valid_coordinate_mask(dataframe),
        "listing_id",
    ].nunique()
    coordinate_coverage = (
        valid_coordinate_listings / total_listings if total_listings else pd.NA
    )
    return {
        "total_listings": total_listings,
        "valid_coordinate_listings": valid_coordinate_listings,
        "coordinate_coverage": coordinate_coverage,
    }


def _validate_columns(dataframe: pd.DataFrame) -> list[str]:
    return sorted(REQUIRED_COLUMNS.difference(dataframe.columns))


def _prepare_overview_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    overview_df = dataframe.copy()
    overview_df["neighbourhood"] = overview_df["neighbourhood"].fillna("UNKNOWN")
    overview_df["room_type"] = overview_df["room_type"].fillna("UNKNOWN")
    overview_df["number_of_reviews"] = pd.to_numeric(
        overview_df["number_of_reviews"],
        errors="coerce",
    ).fillna(0)
    overview_df["review_scores_rating"] = pd.to_numeric(
        overview_df["review_scores_rating"],
        errors="coerce",
    )
    overview_df["estimated_occupancy_l365d"] = pd.to_numeric(
        overview_df["estimated_occupancy_l365d"],
        errors="coerce",
    )
    overview_df["estimated_occupancy_l365d"] = overview_df[
        "estimated_occupancy_l365d"
    ].where(
        overview_df["estimated_occupancy_l365d"].between(0, 365, inclusive="both")
    )
    overview_df["estimated_occupancy_rate_l365d"] = pd.to_numeric(
        overview_df["estimated_occupancy_rate_l365d"],
        errors="coerce",
    )
    overview_df["estimated_occupancy_rate_l365d"] = overview_df[
        "estimated_occupancy_rate_l365d"
    ].where(
        overview_df["estimated_occupancy_rate_l365d"].between(0, 1, inclusive="both")
    )
    overview_df["estimated_revenue_l365d"] = pd.to_numeric(
        overview_df["estimated_revenue_l365d"],
        errors="coerce",
    )
    overview_df["price"] = pd.to_numeric(overview_df["price"], errors="coerce")
    overview_df["latitude"] = pd.to_numeric(overview_df["latitude"], errors="coerce")
    overview_df["longitude"] = pd.to_numeric(overview_df["longitude"], errors="coerce")
    overview_df["host_id"] = pd.to_numeric(overview_df["host_id"], errors="coerce")
    overview_df["is_reliable_review"] = overview_df["is_reliable_review"].fillna(False).astype(bool)
    return overview_df


def _render_filters(dataframe: pd.DataFrame) -> dict[str, list[str]]:
    neighbourhood_options = sorted(dataframe["neighbourhood"].dropna().unique().tolist())
    room_type_options = sorted(dataframe["room_type"].dropna().unique().tolist())

    with st.expander("Market filters", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            selected_neighbourhoods = st.multiselect(
                "Neighbourhood",
                options=neighbourhood_options,
                default=[],
                key="market_overview_neighbourhoods",
            )
        with c2:
            selected_room_types = st.multiselect(
                "Room type",
                options=room_type_options,
                default=[],
                key="market_overview_room_types",
            )

    return {
        "selected_neighbourhoods": selected_neighbourhoods,
        "selected_room_types": selected_room_types,
    }


def _apply_filters(
    dataframe: pd.DataFrame,
    filters: dict[str, list[str]],
) -> pd.DataFrame:
    view = dataframe.copy()
    selected_neighbourhoods = filters["selected_neighbourhoods"]
    selected_room_types = filters["selected_room_types"]

    if selected_neighbourhoods:
        view = view[view["neighbourhood"].isin(selected_neighbourhoods)]
    if selected_room_types:
        view = view[view["room_type"].isin(selected_room_types)]
    return view


def _render_kpis(dataframe: pd.DataFrame) -> None:
    valid_listing_count = dataframe["listing_id"].nunique()
    distinct_hosts = dataframe["host_id"].dropna().nunique()
    price_stats = _price_coverage_stats(dataframe)
    occupancy_stats = _occupancy_coverage_stats(dataframe)
    valid_revenue = dataframe.loc[
        dataframe["estimated_revenue_l365d"].notna() & dataframe["estimated_revenue_l365d"].ge(0),
        "estimated_revenue_l365d",
    ]
    reliable_listing_count = dataframe.loc[dataframe["is_reliable_review"], "listing_id"].nunique()
    reliable_review_coverage = (
        reliable_listing_count / valid_listing_count if valid_listing_count else pd.NA
    )

    render_metric_grid(
        [
            {
                "label": "Listings",
                "value": f"{valid_listing_count:,}",
                "help": "Distinct listing count after applying the current filters.",
            },
            {
                "label": "Unique Hosts",
                "value": f"{distinct_hosts:,}",
                "help": "Distinct non-null hosts represented by the filtered listings.",
            },
            {
                "label": "Median Listed Price",
                "value": _format_thb(price_stats["median_price"]),
                "help": "Median listed nightly price calculated only from listings with a valid price greater than zero.",
                "caption": (
                    f"Price coverage: {_format_pct(price_stats['price_coverage'])} "
                    f"· {price_stats['valid_price_listings']:,} listings"
                ),
            },
            {
                "label": "Median Estimated Occupied Days",
                "value": _format_days(occupancy_stats["median_occupancy_days"]),
                "help": "Median source-derived estimate of occupied days during the trailing 365-day window. A value of 0 means at least half of the included listings have a zero-day estimate.",
                "caption": (
                    "Based on "
                    f"{occupancy_stats['valid_occupancy_listings']:,} of {occupancy_stats['total_listings']:,} "
                    f"listings with valid occupancy estimates ({_format_pct(occupancy_stats['occupancy_coverage'])} coverage)."
                ),
            },
            {
                "label": "Median Estimated Revenue per Listing",
                "value": _format_thb(valid_revenue.median()),
                "help": "Median source-derived estimated revenue per listing during the trailing 365-day window. This is not confirmed transaction revenue.",
            },
            {
                "label": "Review Evidence Coverage",
                "value": _format_pct(reliable_review_coverage),
                "help": "Share of filtered listings with at least five reviews and a non-null overall review score.",
            },
        ],
        cards_per_row=3,
    )
    st.caption(
        "Estimated revenue is a source-derived estimate for relative comparison and should not be interpreted as confirmed transaction revenue."
    )


def _build_supply_map_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    coordinate_view = dataframe.loc[_valid_coordinate_mask(dataframe)].copy()
    if coordinate_view.empty:
        return pd.DataFrame()

    business_summary = (
        dataframe.groupby("neighbourhood", dropna=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "listing_count": frame["listing_id"].nunique(),
                    "median_price": frame.loc[frame["price"] > 0, "price"].median(),
                    "median_estimated_occupancy_days": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "estimated_occupancy_l365d",
                    ].median(),
                    "valid_occupancy_listings": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "listing_id",
                    ].nunique(),
                    "median_estimated_revenue_per_listing": frame.loc[
                        frame["estimated_revenue_l365d"].notna()
                        & frame["estimated_revenue_l365d"].ge(0),
                        "estimated_revenue_l365d",
                    ].median(),
                }
            )
        )
        .reset_index()
    )

    coordinate_summary = (
        coordinate_view.groupby("neighbourhood", dropna=False)
        .agg(
            latitude=("latitude", "median"),
            longitude=("longitude", "median"),
            valid_coordinate_listings=("listing_id", "nunique"),
        )
        .reset_index()
    )

    summary = business_summary.merge(
        coordinate_summary,
        on="neighbourhood",
        how="inner",
    )
    summary["market_share"] = (
        summary["listing_count"] / summary["listing_count"].sum()
        if not summary.empty
        else pd.NA
    )
    dominant_room_type = (
        dataframe.groupby(["neighbourhood", "room_type"], dropna=False)
        .agg(listing_count=("listing_id", "nunique"))
        .reset_index()
        .sort_values(
            ["neighbourhood", "listing_count", "room_type"],
            ascending=[True, False, True],
        )
        .drop_duplicates(subset=["neighbourhood"])
        .rename(columns={"room_type": "dominant_room_type"})
        .loc[:, ["neighbourhood", "dominant_room_type"]]
    )
    summary = summary.merge(dominant_room_type, on="neighbourhood", how="left")
    summary["occupancy_estimate_coverage"] = (
        summary["valid_occupancy_listings"] / summary["listing_count"].replace(0, pd.NA)
    )
    return summary.dropna(subset=["latitude", "longitude"])


def _render_supply_map(dataframe: pd.DataFrame) -> None:
    coordinate_stats = _coordinate_coverage_stats(dataframe)
    summary = _build_supply_map_summary(dataframe)
    if summary.empty:
        st.info("No valid neighbourhood coordinates are available for the current filtered view.")
        st.caption(
            "Map coverage: "
            f"{coordinate_stats['valid_coordinate_listings']:,} of {coordinate_stats['total_listings']:,} "
            f"filtered listings have valid coordinates ({_format_pct(coordinate_stats['coordinate_coverage'])})."
        )
        return

    fig = px.scatter_mapbox(
        summary,
        lat="latitude",
        lon="longitude",
        size="listing_count",
        size_max=34,
        zoom=9,
        hover_name="neighbourhood",
        custom_data=[
            "listing_count",
            "market_share",
            "dominant_room_type",
            "median_price",
        ],
    )
    fig.update_traces(
        hovertemplate=(
            "Neighbourhood: %{hovertext}<br>"
            "Valid Listings: %{customdata[0]:,.0f}<br>"
            "Market Share: %{customdata[1]:.1%}<br>"
            "Dominant Room Type: %{customdata[2]}<br>"
            "Median Listed Price: %{customdata[3]:,.0f} THB"
            "<extra></extra>"
        ),
        marker=dict(color="#0F2742", opacity=0.78),
    )
    fig.update_layout(
        title="Listing Supply by Neighbourhood",
        title_font=dict(size=18, color="#0F2742"),
        height=420,
        margin=dict(l=0, r=0, t=48, b=0),
        mapbox=dict(style="carto-positron"),
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
    if coordinate_stats["coordinate_coverage"] == 1:
        st.caption(
            "Bubble size reflects distinct listing count by neighbourhood. "
            f"Coordinate coverage: {_format_pct(coordinate_stats['coordinate_coverage'])}."
        )
    else:
        st.caption(
            "Bubble size reflects distinct listing count by neighbourhood. "
            f"Map coverage: {coordinate_stats['valid_coordinate_listings']:,} of "
            f"{coordinate_stats['total_listings']:,} filtered listings have valid coordinates "
            f"({_format_pct(coordinate_stats['coordinate_coverage'])})."
        )


def _build_room_type_mix(dataframe: pd.DataFrame) -> pd.DataFrame:
    summary = (
        dataframe.groupby("room_type", dropna=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "listing_count": frame["listing_id"].nunique(),
                    "median_price": frame.loc[frame["price"] > 0, "price"].median(),
                    "median_estimated_occupancy_days": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "estimated_occupancy_l365d",
                    ].median(),
                    "zero_estimate_share": (
                        frame.loc[
                            frame["estimated_occupancy_l365d"].between(0, 365, inclusive="both"),
                            "estimated_occupancy_l365d",
                        ]
                        .eq(0)
                        .mean()
                    ),
                    "reliable_review_coverage": (
                        frame.loc[frame["is_reliable_review"], "listing_id"].nunique()
                        / frame["listing_id"].nunique()
                        if frame["listing_id"].nunique()
                        else pd.NA
                    ),
                    "valid_occupancy_listings": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "listing_id",
                    ].nunique(),
                }
            )
        )
        .reset_index()
    )
    total_listings = summary["listing_count"].sum()
    summary["market_share"] = (
        summary["listing_count"] / total_listings if total_listings else pd.NA
    )
    summary["occupancy_estimate_coverage"] = (
        summary["valid_occupancy_listings"] / summary["listing_count"].replace(0, pd.NA)
    )
    summary["listing_share_label"] = (
        summary["listing_count"].map(lambda value: f"{value:,.0f}")
        + " ("
        + summary["market_share"].map(lambda value: "N/A" if pd.isna(value) else f"{value:.1%}")
        + ")"
    )
    return summary.sort_values("listing_count", ascending=False)


def _render_room_type_mix(dataframe: pd.DataFrame) -> None:
    summary = _build_room_type_mix(dataframe)
    if summary.empty:
        st.info("No room type mix is available under the current filters.")
        return

    ordered_summary = summary.sort_values("listing_count", ascending=True)
    fig = px.bar(
        ordered_summary,
        x="listing_count",
        y="room_type",
        orientation="h",
        title="Listing Mix by Room Type",
        labels={"room_type": "Room Type", "listing_count": "Valid Listings"},
        text="listing_share_label",
    )
    fig.update_traces(
        marker_color="#0F2742",
        texttemplate="%{text}",
        textposition="outside",
        customdata=ordered_summary[
            [
                "market_share",
                "median_price",
                "median_estimated_occupancy_days",
                "zero_estimate_share",
                "reliable_review_coverage",
            ]
        ].values,
        hovertemplate=(
            "Room Type: %{y}<br>"
            "Valid Listings: %{x:,.0f}<br>"
            "Market Share: %{customdata[0]:.1%}<br>"
            "Median Listed Price: %{customdata[1]:,.0f} THB<br>"
            "Median Est. Occupied Days L365D: %{customdata[2]:,.1f} days<br>"
            "Zero-Estimate Share: %{customdata[3]:.1%}<br>"
            "Reliable Review Coverage: %{customdata[4]:.1%}<extra></extra>"
        ),
        cliponaxis=False,
    )
    fig.update_layout(
        title_font=dict(size=18, color="#0F2742"),
        height=360,
        margin=dict(l=0, r=72, t=48, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        xaxis=dict(range=[0, ordered_summary["listing_count"].max() * 1.18 if not ordered_summary.empty else 1]),
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)


def _build_top_neighbourhoods(dataframe: pd.DataFrame) -> pd.DataFrame:
    summary = (
        dataframe.groupby("neighbourhood", dropna=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "listing_count": frame["listing_id"].nunique(),
                    "median_price": frame.loc[frame["price"] > 0, "price"].median(),
                    "median_estimated_occupancy_days": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "estimated_occupancy_l365d",
                    ].median(),
                    "valid_occupancy_listings": frame.loc[
                        _valid_occupancy_listing_mask(frame),
                        "listing_id",
                    ].nunique(),
                }
            )
        )
        .reset_index()
    )
    total_listings = summary["listing_count"].sum()
    summary["market_share"] = (
        summary["listing_count"] / total_listings if total_listings else pd.NA
    )

    dominant_room_type = (
        dataframe.groupby(["neighbourhood", "room_type"], dropna=False)
        .agg(listing_count=("listing_id", "nunique"))
        .reset_index()
        .sort_values(
            ["neighbourhood", "listing_count", "room_type"],
            ascending=[True, False, True],
        )
        .drop_duplicates(subset=["neighbourhood"])
        .rename(columns={"room_type": "dominant_room_type"})
        .loc[:, ["neighbourhood", "dominant_room_type"]]
    )
    summary = summary.merge(dominant_room_type, on="neighbourhood", how="left")
    summary["occupancy_estimate_coverage"] = (
        summary["valid_occupancy_listings"] / summary["listing_count"].replace(0, pd.NA)
    )
    return summary.sort_values("listing_count", ascending=False).head(10)


def _render_top_neighbourhoods(dataframe: pd.DataFrame) -> None:
    summary = _build_top_neighbourhoods(dataframe)
    if summary.empty:
        st.info("No neighbourhood ranking is available under the current filters.")
        return

    ordered = summary.sort_values("listing_count", ascending=True)
    fig = px.bar(
        ordered,
        x="listing_count",
        y="neighbourhood",
        orientation="h",
        title="Top Neighbourhoods by Listing Count",
        labels={"neighbourhood": "Neighbourhood", "listing_count": "Valid Listings"},
        text="listing_count",
    )
    fig.update_traces(
        marker_color="#1F7A8C",
        texttemplate="%{text:,.0f}",
        textposition="outside",
        customdata=ordered[
            [
                "market_share",
                "dominant_room_type",
                "median_price",
                "median_estimated_occupancy_days",
            ]
        ].values,
        hovertemplate=(
            "Neighbourhood: %{y}<br>"
            "Valid Listings: %{x:,.0f}<br>"
            "Market Share: %{customdata[0]:.1%}<br>"
            "Dominant Room Type: %{customdata[1]}<br>"
            "Median Listed Price: %{customdata[2]:,.0f} THB<br>"
            "Median Est. Occupied Days L365D: %{customdata[3]:,.1f} days"
            "<extra></extra>"
        ),
        cliponaxis=False,
    )
    fig.update_layout(
        title_font=dict(size=18, color="#0F2742"),
        height=360,
        margin=dict(l=0, r=16, t=48, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)


def _build_room_type_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    total_listings = dataframe["listing_id"].nunique()
    summary = (
        dataframe.groupby("room_type", dropna=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "Valid Listings": frame["listing_id"].nunique(),
                    "Market Share": (
                        frame["listing_id"].nunique() / total_listings if total_listings else pd.NA
                    ),
                    "Median Listed Price": frame.loc[frame["price"] > 0, "price"].median(),
                    "Median Est. Occupied Days L365D": frame.loc[
                        frame["estimated_occupancy_l365d"].between(0, 365, inclusive="both"),
                        "estimated_occupancy_l365d",
                    ].median(),
                    "Valid Occupancy Listings": frame.loc[
                        frame["estimated_occupancy_l365d"].between(0, 365, inclusive="both"),
                        "listing_id",
                    ].nunique(),
                    "Median Est. Revenue / Listing L365D": frame.loc[
                        frame["estimated_revenue_l365d"].notna()
                        & frame["estimated_revenue_l365d"].ge(0),
                        "estimated_revenue_l365d",
                    ].median(),
                    "Reliable Review Coverage": (
                        frame.loc[frame["is_reliable_review"], "listing_id"].nunique()
                        / frame["listing_id"].nunique()
                        if frame["listing_id"].nunique()
                        else pd.NA
                    ),
                }
            )
        )
        .reset_index()
        .rename(columns={"room_type": "Room Type"})
        .sort_values("Valid Listings", ascending=False)
    )
    summary["Occupancy Estimate Coverage"] = (
        summary["Valid Occupancy Listings"] / summary["Valid Listings"].replace(0, pd.NA)
    )
    if summary["Occupancy Estimate Coverage"].lt(1).any():
        summary = summary[
            [
                "Room Type",
                "Valid Listings",
                "Market Share",
                "Median Listed Price",
                "Median Est. Occupied Days L365D",
                "Occupancy Estimate Coverage",
                "Median Est. Revenue / Listing L365D",
                "Reliable Review Coverage",
            ]
        ]
    else:
        summary = summary[
            [
                "Room Type",
                "Valid Listings",
                "Market Share",
                "Median Listed Price",
                "Median Est. Occupied Days L365D",
                "Median Est. Revenue / Listing L365D",
                "Reliable Review Coverage",
            ]
        ]
    return summary


def _format_room_type_summary(dataframe: pd.DataFrame) -> pd.io.formats.style.Styler:
    formatters = {
        "Valid Listings": "{:,.0f}",
        "Market Share": "{:.1%}",
        "Median Listed Price": "{:,.0f} THB",
        "Median Est. Occupied Days L365D": _format_days,
        "Occupancy Estimate Coverage": "{:.1%}",
        "Median Est. Revenue / Listing L365D": "{:,.0f} THB",
        "Reliable Review Coverage": "{:.1%}",
    }
    active_formatters = {
        column: formatter
        for column, formatter in formatters.items()
        if column in dataframe.columns
    }
    return dataframe.style.format(active_formatters, na_rep="N/A")


def render_executive_overview() -> None:
    st.markdown("#### Market Overview")
    st.caption(
        "Current listing snapshot of supply, room-type mix, and neighbourhood concentration from the Gold layer."
    )

    try:
        overview_df = load_overview_dataset()
    except Exception as exc:  # pragma: no cover
        st.error(f"Cannot load market overview dataset from Gold layer.\n\nError: {exc}")
        return

    if overview_df.empty:
        st.warning("Market overview dataset is empty.")
        return

    missing_columns = _validate_columns(overview_df)
    if missing_columns:
        st.error(
            "Market overview dataset is missing required columns: "
            + ", ".join(missing_columns)
        )
        return

    overview_df = _prepare_overview_dataset(overview_df)
    filters = _render_filters(overview_df)
    filtered = _apply_filters(overview_df, filters)

    if filtered.empty:
        st.warning("No listings match the current filter set.")
        return

    _render_kpis(filtered)
    _render_supply_map(filtered)

    row_left, row_right = two_column_layout([1.0, 1.0])
    with row_left:
        _render_room_type_mix(filtered)
    with row_right:
        _render_top_neighbourhoods(filtered)

    st.markdown("#### Room Type Market Summary")
    st.caption(
        "A median of 0 estimated occupied days means that at least half of the listings in that segment have an estimated occupied-day value of 0. It does not mean that every listing had no bookings."
    )
    summary = _build_room_type_summary(filtered)
    if summary.empty:
        st.info("No room type summary is available under the current filters.")
    else:
        st.dataframe(
            _format_room_type_summary(summary),
            use_container_width=True,
            hide_index=True,
        )
