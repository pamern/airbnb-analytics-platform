from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data_access import load_listing_availability_monthly_dataset
from components.ui import DEFAULT_PLOTLY_CONFIG, render_metric_grid


LISTING_MONTH_REQUIRED_COLUMNS = {
    "listing_id",
    "listing_key",
    "calendar_month",
    "neighbourhood",
    "room_type",
    "available_days",
    "observed_days",
    "availability_share",
    "median_calendar_minimum_nights",
    "price",
    "latitude",
    "longitude",
    "calendar_start_date",
    "calendar_end_date",
}

CAVEAT_TEXT = (
    "Interpretation note: Unavailable dates may reflect bookings, host blocks, "
    "temporary pauses, or other restrictions; they are not confirmed demand or occupancy."
)

def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1%}"


def _format_thb(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} THB"


def _format_days(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} days"


def _format_nights(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} nights"


def _missing_columns(dataframe: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required.difference(dataframe.columns))


def _validate_listing_month_dataset(dataframe: pd.DataFrame) -> None:
    duplicate_mask = dataframe.duplicated(subset=["listing_id", "calendar_month"], keep=False)
    if duplicate_mask.any():
        sample = (
            dataframe.loc[duplicate_mask, ["listing_id", "calendar_month"]]
            .drop_duplicates()
            .head(5)
            .to_dict(orient="records")
        )
        raise ValueError(
            "Location availability monthly dataset returned duplicate listing_id + calendar_month rows. "
            f"Sample duplicates: {sample}"
        )

    invalid_mask = (
        dataframe["available_days"].lt(0)
        | dataframe["observed_days"].le(0)
        | dataframe["available_days"].gt(dataframe["observed_days"])
        | ~dataframe["availability_share"].between(0, 1, inclusive="both")
    )
    if invalid_mask.any():
        raise ValueError(
            "Location availability monthly dataset contains invalid forward availability metrics. "
            "Expected available_days >= 0, observed_days > 0, available_days <= observed_days, "
            "and availability_share between 0 and 1."
        )


def _validate_selected_listing_dataset(dataframe: pd.DataFrame) -> None:
    invalid_mask = (
        dataframe["available_days"].lt(0)
        | dataframe["observed_days"].le(0)
        | dataframe["available_days"].gt(dataframe["observed_days"])
        | ~dataframe["availability_share"].between(0, 1, inclusive="both")
    )
    if invalid_mask.any():
        raise ValueError(
            "Selected listing-period dataset contains invalid forward availability metrics after month aggregation. "
            "This likely indicates an upstream or query issue in the Gold-derived application dataset."
        )


def _valid_coordinate_mask(dataframe: pd.DataFrame) -> pd.Series:
    return (
        dataframe["latitude"].notna()
        & dataframe["longitude"].notna()
        & dataframe["latitude"].between(-90, 90, inclusive="both")
        & dataframe["longitude"].between(-180, 180, inclusive="both")
    )


def _prepare_listing_month_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    listing_month = dataframe.copy()
    listing_month["neighbourhood"] = listing_month["neighbourhood"].fillna("UNKNOWN")
    listing_month["room_type"] = listing_month["room_type"].fillna("UNKNOWN")
    listing_month["calendar_month"] = pd.to_datetime(listing_month["calendar_month"], errors="coerce")
    listing_month["calendar_start_date"] = pd.to_datetime(
        listing_month["calendar_start_date"],
        errors="coerce",
    )
    listing_month["calendar_end_date"] = pd.to_datetime(
        listing_month["calendar_end_date"],
        errors="coerce",
    )

    numeric_columns = [
        "listing_id",
        "available_days",
        "observed_days",
        "availability_share",
        "median_calendar_minimum_nights",
        "price",
        "latitude",
        "longitude",
    ]
    for column in numeric_columns:
        listing_month[column] = pd.to_numeric(listing_month[column], errors="coerce")
    listing_month["listing_key"] = listing_month["listing_key"].astype("string")

    _validate_listing_month_dataset(listing_month)
    return listing_month


def _partial_month_labels(source_start: pd.Timestamp, source_end: pd.Timestamp) -> set[str]:
    labels: set[str] = set()
    if pd.notna(source_start) and source_start.day != 1:
        labels.add(source_start.strftime("%b %Y"))
    if pd.notna(source_end) and source_end.day != source_end.days_in_month:
        labels.add(source_end.strftime("%b %Y"))
    return labels


def _month_label(value: pd.Timestamp, partial_labels: set[str]) -> str:
    label = value.strftime("%b %Y")
    if label in partial_labels:
        return f"{label} · Partial"
    return label


def _render_filters(dataframe: pd.DataFrame) -> dict[str, object]:
    neighbourhood_options = sorted(dataframe["neighbourhood"].dropna().unique().tolist())
    room_type_options = sorted(dataframe["room_type"].dropna().unique().tolist())
    month_values = (
        dataframe["calendar_month"].dropna().drop_duplicates().sort_values().tolist()
    )
    month_labels = [month.strftime("%b %Y") for month in month_values]

    with st.expander("Location & availability filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            selected_neighbourhoods = st.multiselect(
                "Neighbourhood",
                options=neighbourhood_options,
                default=[],
                key="location_availability_neighbourhoods",
            )
        with c2:
            selected_room_types = st.multiselect(
                "Room type",
                options=room_type_options,
                default=[],
                key="location_availability_room_types",
            )
        with c3:
            selected_months = st.multiselect(
                "Calendar month",
                options=month_labels,
                default=[],
                key="location_availability_months",
                help="Leave empty to use all forward-looking calendar months.",
            )
        with c4:
            minimum_listing_count = st.number_input(
                "Minimum listing count",
                min_value=1,
                value=10,
                step=1,
                key="location_availability_min_listing_count",
                help=(
                    "Minimum number of calendar listings required for neighbourhood-level "
                    "comparisons. Market-level KPIs and the monthly trend are not affected."
                ),
            )

    return {
        "selected_neighbourhoods": selected_neighbourhoods,
        "selected_room_types": selected_room_types,
        "selected_months": selected_months,
        "minimum_listing_count": int(minimum_listing_count),
    }


def _apply_filters(
    dataframe: pd.DataFrame,
    filters: dict[str, object],
) -> pd.DataFrame:
    filtered = dataframe.copy()
    selected_neighbourhoods = filters["selected_neighbourhoods"]
    selected_room_types = filters["selected_room_types"]
    selected_months = filters["selected_months"]

    if selected_neighbourhoods:
        filtered = filtered[filtered["neighbourhood"].isin(selected_neighbourhoods)]
    if selected_room_types:
        filtered = filtered[filtered["room_type"].isin(selected_room_types)]
    if selected_months:
        month_map = {
            value.strftime("%b %Y"): value
            for value in filtered["calendar_month"].dropna().drop_duplicates().tolist()
        }
        selected_month_values = [month_map[label] for label in selected_months if label in month_map]
        filtered = filtered[filtered["calendar_month"].isin(selected_month_values)]
    return filtered


def _aggregate_selected_listing_period(dataframe: pd.DataFrame) -> pd.DataFrame:
    listing_period = (
        dataframe.groupby("listing_id", dropna=False)
        .agg(
            listing_key=("listing_key", "first"),
            neighbourhood=("neighbourhood", "first"),
            room_type=("room_type", "first"),
            available_days=("available_days", "sum"),
            observed_days=("observed_days", "sum"),
            median_calendar_minimum_nights=(
                "median_calendar_minimum_nights",
                lambda series: series[series > 0].median(),
            ),
            price=("price", "first"),
            latitude=("latitude", "median"),
            longitude=("longitude", "median"),
        )
        .reset_index()
    )
    listing_period["availability_share"] = (
        listing_period["available_days"] / listing_period["observed_days"].replace(0, pd.NA)
    )
    _validate_selected_listing_dataset(listing_period)
    return listing_period


def _selected_period_label(dataframe: pd.DataFrame) -> str:
    months = dataframe["calendar_month"].dropna().drop_duplicates().sort_values().tolist()
    if not months:
        return "Selected: N/A"
    if len(months) == 1:
        return f"Selected: {months[0]:%b %Y}"

    contiguous = all(
        months[index] == (months[index - 1] + pd.DateOffset(months=1))
        for index in range(1, len(months))
    )
    if contiguous:
        return f"Selected: {months[0]:%b %Y} - {months[-1]:%b %Y}"

    return "Selected months: " + ", ".join(month.strftime("%b %Y") for month in months)


def _render_kpis(
    listing_period_df: pd.DataFrame,
    filtered_month_df: pd.DataFrame,
) -> None:
    neighbourhood_count = listing_period_df.loc[
        listing_period_df["observed_days"].gt(0),
        "neighbourhood",
    ].nunique()
    listings_with_calendar = listing_period_df["listing_id"].nunique()
    forward_availability_share = (
        filtered_month_df["available_days"].sum()
        / filtered_month_df["observed_days"].sum()
        if filtered_month_df["observed_days"].sum()
        else pd.NA
    )
    median_available_days = listing_period_df["available_days"].median()
    median_calendar_minimum_nights = listing_period_df.loc[
        listing_period_df["median_calendar_minimum_nights"] > 0,
        "median_calendar_minimum_nights",
    ].median()
    valid_price = listing_period_df.loc[listing_period_df["price"] > 0, "price"]
    price_coverage = (
        listing_period_df.loc[listing_period_df["price"] > 0, "listing_id"].nunique()
        / listings_with_calendar
        if listings_with_calendar
        else pd.NA
    )

    render_metric_grid(
        [
            {
                "label": "Neighbourhoods Covered",
                "value": f"{neighbourhood_count:,}",
                "help": "Distinct neighbourhoods with observed listing-days greater than zero in the selected period.",
            },
            {
                "label": "Listings with Calendar Data",
                "value": f"{listings_with_calendar:,}",
                "help": "Distinct listings represented in fact_availability_daily during the selected period.",
            },
            {
                "label": "Forward Availability Share",
                "value": _format_pct(forward_availability_share),
                "help": "Weighted share of observed listing-days marked as available during the selected period.",
            },
            {
                "label": "Median Available Days per Listing",
                "value": _format_days(median_available_days),
                "help": (
                    "Median listing-level total of available days during the selected period. "
                    "It does not need to equal the overall weighted availability share."
                ),
            },
            {
                "label": "Median Monthly Minimum Nights",
                "value": _format_nights(median_calendar_minimum_nights),
                "help": (
                    "Median of listing-month minimum-night medians across the selected "
                    "calendar months; it is not calculated directly from all daily rows."
                ),
            },
            {
                "label": "Median Listed Price",
                "value": _format_thb(valid_price.median()),
                "help": "Current snapshot price used only as listing metadata, not as a monthly historical price.",
                "caption": f"Snapshot price · {_format_pct(price_coverage)} coverage",
            },
        ],
        cards_per_row=3,
    )


def _build_neighbourhood_summary(listing_period_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        listing_period_df.groupby("neighbourhood", dropna=False)
        .agg(
            listings_with_calendar_data=("listing_id", "nunique"),
            available_days=("available_days", "sum"),
            observed_listing_days=("observed_days", "sum"),
            median_available_days_per_listing=("available_days", "median"),
            median_calendar_minimum_nights=(
                "median_calendar_minimum_nights",
                lambda series: series[series > 0].median(),
            ),
            median_listed_price=("price", lambda series: series[series > 0].median()),
            latitude=("latitude", "median"),
            longitude=("longitude", "median"),
        )
        .reset_index()
    )
    summary["forward_availability_share"] = (
        summary["available_days"] / summary["observed_listing_days"].replace(0, pd.NA)
    )
    return summary


def _render_supply_map(
    listing_period_df: pd.DataFrame,
    neighbourhood_summary: pd.DataFrame,
    minimum_listing_count: int,
) -> None:
    eligible = neighbourhood_summary[
        neighbourhood_summary["listings_with_calendar_data"] >= minimum_listing_count
    ].copy()
    coordinate_mask = _valid_coordinate_mask(listing_period_df)
    total_listings = listing_period_df["listing_id"].nunique()
    listings_with_coordinates = listing_period_df.loc[coordinate_mask, "listing_id"].nunique()
    coordinate_coverage = (
        listings_with_coordinates / total_listings if total_listings else pd.NA
    )

    map_view = eligible[
        eligible["latitude"].between(-90, 90, inclusive="both")
        & eligible["longitude"].between(-180, 180, inclusive="both")
    ].copy()
    if map_view.empty:
        st.info("No eligible neighbourhoods with valid coordinates are available for the current filtered view.")
        st.caption(
            "Map coordinate coverage: "
            f"{listings_with_coordinates:,} of {total_listings:,} listings with calendar data have valid coordinates "
            f"({_format_pct(coordinate_coverage)})."
        )
        return

    fig = px.scatter_mapbox(
        map_view,
        lat="latitude",
        lon="longitude",
        size="listings_with_calendar_data",
        color="forward_availability_share",
        color_continuous_scale=["#F4F6F8", "#7FB3D5", "#0F2742"],
        size_max=28,
        zoom=9.4,
        hover_name="neighbourhood",
        custom_data=[
            "forward_availability_share",
            "listings_with_calendar_data",
            "observed_listing_days",
            "median_available_days_per_listing",
            "median_listed_price",
        ],
    )
    fig.update_traces(
        hovertemplate=(
            "Neighbourhood: %{hovertext}<br>"
            "Forward Availability Share: %{customdata[0]:.1%}<br>"
            "Listings with Calendar Data: %{customdata[1]:,.0f}<br>"
            "Observed Listing-Days: %{customdata[2]:,.0f}<br>"
            "Median Available Days per Listing: %{customdata[3]:,.0f} days<br>"
            "Median Listed Price: %{customdata[4]:,.0f} THB<extra></extra>"
        ),
        marker=dict(opacity=0.68),
    )
    fig.update_layout(
        title="Forward Availability by Neighbourhood",
        title_font=dict(size=18, color="#0F2742"),
        height=420,
        margin=dict(l=0, r=0, t=48, b=0),
        mapbox=dict(style="carto-positron"),
        paper_bgcolor="white",
        coloraxis_colorbar=dict(title="Forward Availability Share", tickformat=".0%"),
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
    st.caption(
        "Bubble size reflects listings with calendar data. "
        f"Map coordinate coverage: {listings_with_coordinates:,} of {total_listings:,} listings with calendar data have valid coordinates "
        f"({_format_pct(coordinate_coverage)})."
    )


def _render_monthly_availability(
    month_df: pd.DataFrame,
    partial_labels: set[str],
) -> None:
    summary = (
        month_df.groupby("calendar_month", dropna=False)
        .agg(
            available_listing_days=("available_days", "sum"),
            observed_listing_days=("observed_days", "sum"),
            distinct_listings=("listing_id", "nunique"),
        )
        .reset_index()
        .sort_values("calendar_month")
    )
    if summary.empty:
        st.info("No forward availability months are available under the current filters.")
        return

    summary["forward_availability_share"] = (
        summary["available_listing_days"] / summary["observed_listing_days"].replace(0, pd.NA)
    )
    summary["calendar_month_display"] = summary["calendar_month"].apply(
        lambda value: _month_label(value, partial_labels)
    )
    fig = px.line(
        summary,
        x="calendar_month_display",
        y="forward_availability_share",
        markers=True,
        title="Forward Availability Trend by Month",
        labels={
            "calendar_month_display": "Calendar Month",
            "forward_availability_share": "Forward Availability Share",
        },
    )
    fig.update_traces(
        line_color="#0F2742",
        marker_color="#1F7A8C",
        customdata=summary[
            [
                "available_listing_days",
                "observed_listing_days",
                "distinct_listings",
            ]
        ].values,
        hovertemplate=(
            "Calendar Month: %{x}<br>"
            "Forward Availability Share: %{y:.1%}<br>"
            "Available Listing-Days: %{customdata[0]:,.0f}<br>"
            "Observed Listing-Days: %{customdata[1]:,.0f}<br>"
            "Distinct Listings: %{customdata[2]:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        title_font=dict(size=18, color="#0F2742"),
        height=360,
        margin=dict(l=0, r=0, t=48, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis_tickformat=".0%",
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)


def _render_availability_ranking(
    neighbourhood_summary: pd.DataFrame,
    minimum_listing_count: int,
) -> None:
    eligible = neighbourhood_summary[
        neighbourhood_summary["listings_with_calendar_data"] >= minimum_listing_count
    ].copy()
    if eligible.empty:
        st.info("No neighbourhoods meet the current minimum listing count threshold.")
        return

    highest_tab, lowest_tab = st.tabs(["Highest", "Lowest"])
    for tab_name, container in [("highest", highest_tab), ("lowest", lowest_tab)]:
        with container:
            if tab_name == "highest":
                ranking = eligible.sort_values(
                    ["forward_availability_share", "listings_with_calendar_data"],
                    ascending=[False, False],
                ).head(10)
            else:
                ranking = eligible.sort_values(
                    ["forward_availability_share", "listings_with_calendar_data"],
                    ascending=[True, False],
                ).head(10)
            ordered = ranking.sort_values("forward_availability_share", ascending=True)
            fig = px.bar(
                ordered,
                x="forward_availability_share",
                y="neighbourhood",
                orientation="h",
                title=(
                    "Highest-Availability Neighbourhoods"
                    if tab_name == "highest"
                    else "Lowest-Availability Neighbourhoods"
                ),
                labels={
                    "forward_availability_share": "Forward Availability Share",
                    "neighbourhood": "Neighbourhood",
                },
                text="forward_availability_share",
            )
            fig.update_traces(
                marker_color="#0F2742" if tab_name == "highest" else "#BF6C32",
                texttemplate="%{text:.1%}",
                textposition="outside",
                customdata=ordered[
                    [
                        "listings_with_calendar_data",
                        "median_available_days_per_listing",
                        "median_listed_price",
                    ]
                ].values,
                hovertemplate=(
                    "Neighbourhood: %{y}<br>"
                    "Forward Availability Share: %{x:.1%}<br>"
                    "Listings with Calendar Data: %{customdata[0]:,.0f}<br>"
                    "Median Available Days: %{customdata[1]:,.0f} days<br>"
                    "Median Listed Price: %{customdata[2]:,.0f} THB<extra></extra>"
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
                xaxis_tickformat=".0%",
            )
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)


def _render_price_vs_availability_scatter(
    neighbourhood_summary: pd.DataFrame,
    minimum_listing_count: int,
) -> None:
    eligible = neighbourhood_summary[
        neighbourhood_summary["listings_with_calendar_data"] >= minimum_listing_count
    ].copy()
    if eligible.empty:
        st.info("No neighbourhoods meet the current minimum listing count threshold for the scatter plot.")
        return

    fig = px.scatter(
        eligible,
        x="median_listed_price",
        y="forward_availability_share",
        size="listings_with_calendar_data",
        title="Price vs Forward Availability by Neighbourhood",
        labels={
            "median_listed_price": "Median Listed Price (THB)",
            "forward_availability_share": "Forward Availability Share",
        },
        hover_name="neighbourhood",
        custom_data=[
            "median_listed_price",
            "forward_availability_share",
            "listings_with_calendar_data",
            "median_calendar_minimum_nights",
        ],
    )
    fig.update_traces(
        hovertemplate=(
            "Neighbourhood: %{hovertext}<br>"
            "Median Listed Price: %{customdata[0]:,.0f} THB<br>"
            "Forward Availability Share: %{customdata[1]:.1%}<br>"
            "Listings with Calendar Data: %{customdata[2]:,.0f}<br>"
            "Median Monthly Minimum Nights: %{customdata[3]:,.0f} nights<extra></extra>"
        ),
        marker=dict(opacity=0.8, color="#1F7A8C"),
    )
    fig.update_layout(
        title_font=dict(size=18, color="#0F2742"),
        height=380,
        margin=dict(l=0, r=0, t=48, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis_tickformat=".0%",
        showlegend=False,
    )
    median_price = eligible["median_listed_price"].median()
    overall_availability = (
        eligible["available_days"].sum() / eligible["observed_listing_days"].sum()
        if eligible["observed_listing_days"].sum()
        else pd.NA
    )
    if pd.notna(median_price):
        fig.add_vline(x=median_price, line_width=1, line_dash="dot", line_color="#7A8797")
    if pd.notna(overall_availability):
        fig.add_hline(y=overall_availability, line_width=1, line_dash="dot", line_color="#7A8797")
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
    st.caption("This chart shows association only and should not be interpreted as evidence of causation.")


def _render_availability_heatmap(
    filtered_month_df: pd.DataFrame,
    neighbourhood_summary: pd.DataFrame,
    minimum_listing_count: int,
    partial_labels: set[str],
) -> None:
    eligible_neighbourhoods = neighbourhood_summary[
        neighbourhood_summary["listings_with_calendar_data"] >= minimum_listing_count
    ].sort_values("listings_with_calendar_data", ascending=False).head(10)["neighbourhood"].tolist()
    heatmap_source = filtered_month_df[filtered_month_df["neighbourhood"].isin(eligible_neighbourhoods)].copy()
    if heatmap_source["calendar_month"].nunique() < 2 or heatmap_source["neighbourhood"].nunique() < 2:
        st.info("Not enough months or neighbourhoods are available to render the availability heatmap.")
        return

    summary = (
        heatmap_source.groupby(["neighbourhood", "calendar_month"], dropna=False)
        .agg(
            available_listing_days=("available_days", "sum"),
            observed_listing_days=("observed_days", "sum"),
            listings_with_calendar_data=("listing_id", "nunique"),
        )
        .reset_index()
    )
    summary["forward_availability_share"] = (
        summary["available_listing_days"] / summary["observed_listing_days"].replace(0, pd.NA)
    )
    summary["calendar_month_label"] = summary["calendar_month"].apply(
        lambda value: _month_label(value, partial_labels)
    )

    month_order = (
        summary.loc[:, ["calendar_month", "calendar_month_label"]]
        .drop_duplicates()
        .sort_values("calendar_month")["calendar_month_label"]
        .tolist()
    )

    z_values = []
    custom_values = []
    for neighbourhood in eligible_neighbourhoods:
        row_z = []
        row_custom = []
        for month_label in month_order:
            cell = summary[
                (summary["neighbourhood"] == neighbourhood)
                & (summary["calendar_month_label"] == month_label)
            ]
            if cell.empty:
                row_z.append(None)
                row_custom.append([None, None])
            else:
                row_z.append(cell["forward_availability_share"].iloc[0])
                row_custom.append(
                    [
                        cell["listings_with_calendar_data"].iloc[0],
                        cell["observed_listing_days"].iloc[0],
                    ]
                )
        z_values.append(row_z)
        custom_values.append(row_custom)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=month_order,
            y=eligible_neighbourhoods,
            customdata=custom_values,
            colorscale=[[0.0, "#F4F6F8"], [0.5, "#7FB3D5"], [1.0, "#0F2742"]],
            colorbar=dict(title="Forward Availability Share", tickformat=".0%"),
            hovertemplate=(
                "Neighbourhood: %{y}<br>"
                "Calendar Month: %{x}<br>"
                "Forward Availability Share: %{z:.1%}<br>"
                "Listings with Calendar Data: %{customdata[0]:,.0f}<br>"
                "Observed Listing-Days: %{customdata[1]:,.0f}<extra></extra>"
            ),
            zmin=0,
            zmax=1,
            text=[
                ["" if value is None or pd.isna(value) else f"{value:.0%}" for value in row]
                for row in z_values
            ],
            texttemplate="%{text}",
            textfont=dict(color="#0F2742", size=10),
        )
    )
    fig.update_layout(
        title="Availability by Neighbourhood and Month",
        title_font=dict(size=18, color="#0F2742"),
        height=420,
        margin=dict(l=0, r=0, t=48, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)


def _build_benchmark_table(
    neighbourhood_summary: pd.DataFrame,
    minimum_listing_count: int,
) -> pd.DataFrame:
    benchmark = neighbourhood_summary[
        neighbourhood_summary["listings_with_calendar_data"] >= minimum_listing_count
    ].copy()
    return benchmark.rename(
        columns={
            "neighbourhood": "Neighbourhood",
            "listings_with_calendar_data": "Calendar Listings",
            "forward_availability_share": "Availability Share",
            "median_available_days_per_listing": "Median Available Days",
            "median_calendar_minimum_nights": "Median Min. Nights",
            "median_listed_price": "Median Price",
            "observed_listing_days": "Observed Listing-Days",
        }
    )[
        [
            "Neighbourhood",
            "Calendar Listings",
            "Availability Share",
            "Median Available Days",
            "Median Min. Nights",
            "Median Price",
            "Observed Listing-Days",
        ]
    ].sort_values("Calendar Listings", ascending=False)


def render_location_availability_performance() -> None:
    st.markdown("#### Location & Forward Availability")
    st.caption(
        "Forward-looking calendar availability by neighbourhood, room type, and selected time period from the Gold layer."
    )
    st.markdown(
        (
            "<div style='padding:0.45rem 0.7rem; margin:0.2rem 0 0.45rem 0; "
            "background:#F6F8FA; border:1px solid #D9DEE5; border-radius:0.5rem; "
            "font-size:0.9rem; color:#3D4754;'>"
            f"{CAVEAT_TEXT}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    try:
        listing_month_df = load_listing_availability_monthly_dataset()
    except Exception as exc:  # pragma: no cover
        st.error(f"Cannot load location & availability datasets from Gold layer.\n\nError: {exc}")
        return

    if listing_month_df.empty:
        st.warning("Location & availability dataset is empty.")
        return

    missing_columns = _missing_columns(listing_month_df, LISTING_MONTH_REQUIRED_COLUMNS)
    if missing_columns:
        st.error(
            "Location & availability dataset is missing required columns: "
            + ", ".join(missing_columns)
        )
        return

    listing_month_df = _prepare_listing_month_dataset(listing_month_df)
    filters = _render_filters(listing_month_df)
    filtered_month_df = _apply_filters(listing_month_df, filters)

    if filtered_month_df.empty:
        st.warning("No forward calendar records match the current filter set.")
        return

    source_start = listing_month_df["calendar_start_date"].dropna().min()
    source_end = listing_month_df["calendar_end_date"].dropna().max()
    partial_labels = _partial_month_labels(source_start, source_end)
    selected_label = (
        "Selected: All available months"
        if not filters["selected_months"]
        else _selected_period_label(filtered_month_df)
    )
    if pd.notna(source_start) and pd.notna(source_end):
        st.caption(
            f"Source coverage: {source_start:%d %b %Y}-{source_end:%d %b %Y} · {selected_label}"
        )
    if partial_labels:
        st.caption("The first and last calendar months are partial.")

    listing_period_df = _aggregate_selected_listing_period(filtered_month_df)
    neighbourhood_summary = _build_neighbourhood_summary(listing_period_df)

    _render_kpis(listing_period_df, filtered_month_df)
    _render_supply_map(
        listing_period_df,
        neighbourhood_summary,
        minimum_listing_count=int(filters["minimum_listing_count"]),
    )

    _render_monthly_availability(filtered_month_df, partial_labels)
    _render_availability_ranking(
        neighbourhood_summary,
        minimum_listing_count=int(filters["minimum_listing_count"]),
    )

    _render_price_vs_availability_scatter(
        neighbourhood_summary,
        minimum_listing_count=int(filters["minimum_listing_count"]),
    )

    with st.expander("Availability pattern explorer", expanded=False):
        _render_availability_heatmap(
            filtered_month_df,
            neighbourhood_summary,
            minimum_listing_count=int(filters["minimum_listing_count"]),
            partial_labels=partial_labels,
        )

    st.markdown("#### Neighbourhood Availability Benchmark")
    benchmark = _build_benchmark_table(
        neighbourhood_summary,
        minimum_listing_count=int(filters["minimum_listing_count"]),
    )
    if benchmark.empty:
        st.info("No neighbourhoods meet the current minimum listing count threshold for the benchmark table.")
    else:
        benchmark_display = benchmark.copy()
        benchmark_display["Availability Share"] = benchmark_display["Availability Share"] * 100
        st.dataframe(
            benchmark_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Neighbourhood": st.column_config.TextColumn(width="medium"),
                "Calendar Listings": st.column_config.NumberColumn(width="small", format="%d"),
                "Availability Share": st.column_config.NumberColumn(width="small", format="%.1f%%"),
                "Median Available Days": st.column_config.NumberColumn(width="small", format="%d days"),
                "Median Min. Nights": st.column_config.NumberColumn(width="small", format="%d nights"),
                "Median Price": st.column_config.NumberColumn(width="small", format="%d THB"),
                "Observed Listing-Days": st.column_config.NumberColumn(width="medium", format="%d"),
            },
        )
