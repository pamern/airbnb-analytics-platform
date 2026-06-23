from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data_access import load_host_quality_dataset, load_listing_review_recency_dataset
from components.ui import DEFAULT_PLOTLY_CONFIG, render_metric_grid, two_column_layout


def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1%}"


def _format_score(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}"


def _assign_host_size_group(total_listings: float | int | None) -> str:
    if pd.isna(total_listings):
        return "Unknown"
    if total_listings <= 1:
        return "Solo"
    if total_listings <= 5:
        return "Small"
    if total_listings <= 20:
        return "Medium"
    return "Large"


def _render_filters(host_quality: pd.DataFrame) -> dict[str, object]:
    with st.expander("Host & review filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)

        neighbourhood_options = sorted(host_quality["neighbourhood"].dropna().unique().tolist())
        room_type_options = sorted(host_quality["room_type"].dropna().unique().tolist())
        host_size_options = ["Solo", "Small", "Medium", "Large", "Unknown"]

        with c1:
            selected_neighbourhoods = st.multiselect(
                "Neighbourhood",
                options=neighbourhood_options,
                default=[],
                key="host_neighbourhoods",
            )
        with c2:
            selected_room_types = st.multiselect(
                "Room type",
                options=room_type_options,
                default=[],
                key="host_room_types",
            )
        with c3:
            selected_host_sizes = st.multiselect(
                "Host size",
                options=host_size_options,
                default=[],
                key="host_size_groups",
            )
        with c4:
            verified_only = st.toggle(
                "Verified hosts only",
                value=False,
                key="host_verified_only",
            )
        if verified_only:
            st.caption(
                "Verified Host Share reflects the filtered population when 'Verified hosts only' is enabled."
            )

    return {
        "selected_neighbourhoods": selected_neighbourhoods,
        "selected_room_types": selected_room_types,
        "selected_host_sizes": selected_host_sizes,
        "verified_only": verified_only,
    }


def _apply_filters(
    host_quality: pd.DataFrame,
    filters: dict[str, object],
) -> pd.DataFrame:
    host_view = host_quality.copy()

    selected_neighbourhoods = filters["selected_neighbourhoods"]
    selected_room_types = filters["selected_room_types"]
    selected_host_sizes = filters["selected_host_sizes"]
    verified_only = filters["verified_only"]

    if selected_neighbourhoods:
        host_view = host_view[host_view["neighbourhood"].isin(selected_neighbourhoods)]
    if selected_room_types:
        host_view = host_view[host_view["room_type"].isin(selected_room_types)]
    if selected_host_sizes:
        host_view = host_view[host_view["host_size_group"].isin(selected_host_sizes)]
    if verified_only:
        host_view = host_view[host_view["host_identity_verified"].fillna(False)]

    return host_view


def _render_kpis(host_view: pd.DataFrame) -> None:
    host_unique = host_view.sort_values(["host_id", "listing_id"]).drop_duplicates("host_id")
    superhost_share = host_unique["host_is_superhost"].fillna(False).mean()
    verified_share = host_unique["host_identity_verified"].fillna(False).mean()
    reliable_review_view = host_view[host_view["is_reliable_review"]].copy()
    total_listings = host_view["listing_id"].nunique()
    reliable_listings = reliable_review_view["listing_id"].nunique()
    reliable_review_coverage = (
        reliable_listings / total_listings if total_listings else pd.NA
    )

    render_metric_grid(
        [
            {
                "label": "Total Hosts",
                "value": f"{host_unique['host_id'].nunique():,}",
                "help": "Distinct hosts in the current filtered view.",
            },
            {
                "label": "Superhost Share",
                "value": _format_pct(superhost_share),
                "help": "Share of distinct hosts marked as superhosts.",
            },
            {
                "label": "Verified Host Share",
                "value": _format_pct(verified_share),
                "help": "Share of distinct hosts with identity verified.",
            },
            {
                "label": "Median Acceptance Rate",
                "value": _format_pct(host_unique["host_acceptance_rate"].median()),
                "help": "Median host acceptance rate across distinct hosts.",
            },
            {
                "label": "Median Review Score",
                "value": _format_score(reliable_review_view["review_scores_rating"].median()),
                "help": "Median review score across reliable listings only: number_of_reviews >= 5 and rating not null.",
            },
            {
                "label": "Reliable Review Coverage",
                "value": _format_pct(reliable_review_coverage),
                "help": "Reliable listings divided by all filtered listings, where reliable means number_of_reviews >= 5 and rating not null.",
            },
        ],
        cards_per_row=3,
    )
    st.caption(
        "Host rates and review scores are snapshot-based indicators from the Gold layer. Use them for relative comparison across host segments, not as audited service-level guarantees."
    )


def _build_superhost_comparison(host_view: pd.DataFrame) -> go.Figure:
    reliable_view = host_view[host_view["is_reliable_review"]].copy()
    if reliable_view.empty:
        return go.Figure()

    review_summary = (
        reliable_view.assign(
            host_tier=reliable_view["host_is_superhost"].map({True: "Superhost", False: "Non-superhost"})
        )
        .groupby("host_tier", as_index=False)
        .agg(
            median_review_score=("review_scores_rating", "median"),
            listing_count=("listing_id", "nunique"),
        )
    )
    host_summary = (
        host_view.sort_values(["host_id", "listing_id"])
        .drop_duplicates("host_id")
        .assign(
            host_tier=lambda df: df["host_is_superhost"].map(
                {True: "Superhost", False: "Non-superhost"}
            )
        )
        .groupby("host_tier", as_index=False)
        .agg(
            median_response_rate=("host_response_rate", "median"),
            host_count=("host_id", "nunique"),
        )
    )
    summary = review_summary.merge(host_summary, on="host_tier", how="left")

    fig = go.Figure()
    fig.add_bar(
        x=summary["host_tier"],
        y=summary["median_review_score"],
        text=summary["median_review_score"].map(lambda value: f"{value:.2f}"),
        textposition="outside",
        marker_color=["#0F2742", "#94A3B8"],
        customdata=summary[["median_response_rate", "listing_count", "host_count"]].values,
        hovertemplate=(
            "Host tier: %{x}<br>"
            "Median review score: %{y:.2f}<br>"
            "Median response rate: %{customdata[0]:.1%}<br>"
            "Reliable listings: %{customdata[1]:,.0f}<br>"
            "Distinct hosts: %{customdata[2]:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        title="Review Quality by Host Tier",
        title_font=dict(size=18, color="#0F2742"),
        xaxis_title="Host tier",
        yaxis_title="Median Review Score",
        height=340,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def _build_review_dimension_profile(host_view: pd.DataFrame) -> go.Figure:
    reliable_view = host_view[host_view["is_reliable_review"]].copy()
    mapping = {
        "review_scores_accuracy": "Accuracy",
        "review_scores_cleanliness": "Cleanliness",
        "review_scores_checkin": "Check-in",
        "review_scores_communication": "Communication",
        "review_scores_location": "Location",
        "review_scores_value": "Value",
    }
    if reliable_view.empty:
        return go.Figure()

    summary = (
        reliable_view.loc[:, mapping.keys()]
        .mean()
        .rename(index=mapping)
        .reset_index()
    )
    summary.columns = ["dimension", "score"]
    summary = summary.sort_values("score", ascending=True)
    if summary.empty:
        return go.Figure()

    fig = px.bar(
        summary,
        x="score",
        y="dimension",
        orientation="h",
        title="Review Dimension Breakdown",
        labels={"dimension": "Review dimension", "score": "Average score"},
    )
    fig.update_traces(
        marker_color="#0F2742",
        text=summary["score"].map(lambda value: f"{value:.2f}"),
        textposition="outside",
        hovertemplate="Dimension: %{y}<br>Average score: %{x:.2f}<extra></extra>",
    )
    fig.update_layout(
        title_font=dict(size=18, color="#0F2742"),
        height=340,
        margin=dict(l=0, r=40, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _build_host_size_operations(host_view: pd.DataFrame) -> go.Figure:
    host_unique = host_view.sort_values(["host_id", "listing_id"]).drop_duplicates("host_id").copy()
    summary = (
        host_unique.groupby("host_size_group", as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "host_count": frame["host_id"].nunique(),
                    "valid_hosts": frame["host_acceptance_rate"].notna().sum(),
                    "risk_hosts": frame["host_acceptance_rate"].lt(0.8).fillna(False).sum(),
                }
            )
        )
        .reset_index(drop=True)
    )
    summary["acceptance_risk_share"] = summary["risk_hosts"] / summary["valid_hosts"].replace(0, pd.NA)
    summary["host_size_group"] = pd.Categorical(
        summary["host_size_group"],
        categories=["Solo", "Small", "Medium", "Large", "Unknown"],
        ordered=True,
    )
    summary = summary.sort_values("host_size_group")
    summary = summary[summary["valid_hosts"] > 0]
    if summary.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_bar(
        x=summary["host_size_group"],
        y=summary["acceptance_risk_share"],
        name="Acceptance rate < 80%",
        marker_color="#0F2742",
        text=summary["acceptance_risk_share"].map(lambda value: f"{value:.1%}"),
        textposition="outside",
        customdata=summary[["risk_hosts", "valid_hosts", "host_count"]].values,
        hovertemplate=(
            "Host size: %{x}<br>"
            "Hosts with acceptance rate < 80%: %{y:.1%}<br>"
            "Risk hosts: %{customdata[0]:,.0f}<br>"
            "Valid hosts: %{customdata[1]:,.0f}<br>"
            "Total hosts: %{customdata[2]:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        title="Acceptance Risk by Host Size",
        title_font=dict(size=18, color="#0F2742"),
        xaxis_title="Host size",
        yaxis_title="Share of Hosts",
        height=340,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return fig


def _build_review_quality_distribution(host_view: pd.DataFrame) -> go.Figure:
    distribution_view = host_view.copy()
    if distribution_view.empty:
        return go.Figure()

    def classify_band(row: pd.Series) -> str:
        if (row["number_of_reviews"] < 5) or pd.isna(row["review_scores_rating"]):
            return "Insufficient Evidence"
        if row["review_scores_rating"] < 4.0:
            return "Low Rating"
        if row["review_scores_rating"] < 4.5:
            return "Moderate"
        if row["review_scores_rating"] < 4.8:
            return "Good"
        return "Excellent"

    distribution_view["review_quality_band"] = distribution_view.apply(classify_band, axis=1)
    summary = (
        distribution_view.groupby("review_quality_band", as_index=False)
        .agg(listings=("listing_id", "nunique"))
    )
    summary["review_quality_band"] = pd.Categorical(
        summary["review_quality_band"],
        categories=[
            "Insufficient Evidence",
            "Low Rating",
            "Moderate",
            "Good",
            "Excellent",
        ],
        ordered=True,
    )
    summary = summary.sort_values("review_quality_band")
    if summary.empty:
        return go.Figure()

    fig = px.bar(
        summary,
        x="review_quality_band",
        y="listings",
        title="Listing Review Quality Distribution",
        labels={
            "review_quality_band": "Review quality band",
            "listings": "Listings",
        },
    )
    fig.update_traces(
        marker_color="#0F2742",
        text=summary["listings"].map(lambda value: f"{value:,.0f}"),
        textposition="outside",
        hovertemplate="Band: %{x}<br>Listings: %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        title="Listing Review Quality Distribution",
        title_font=dict(size=18, color="#0F2742"),
        title_x=0.0,
        xaxis_title="Review quality band",
        yaxis_title="Listings",
        height=360,
        margin=dict(l=0, r=0, t=56, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def _build_review_score_vs_evidence(host_view: pd.DataFrame) -> go.Figure:
    score_view = host_view.dropna(subset=["review_scores_rating"]).copy()
    if score_view.empty:
        return go.Figure()

    score_view["review_count_display"] = score_view["number_of_reviews"].clip(lower=0)
    review_cap = score_view["review_count_display"].quantile(0.99)
    if pd.notna(review_cap) and review_cap > 0:
        score_view["review_count_display"] = score_view["review_count_display"].clip(upper=review_cap)

    median_score = score_view["review_scores_rating"].median()
    fig = px.scatter(
        score_view,
        x="review_count_display",
        y="review_scores_rating",
        color="is_reliable_review",
        color_discrete_map={True: "#0F2742", False: "#BF6C32"},
        title="Review Score vs Review Evidence",
        labels={
            "review_count_display": "Number of reviews",
            "review_scores_rating": "Review score",
            "is_reliable_review": "Reliable review",
        },
        hover_data={
            "listing_name": True,
            "neighbourhood": True,
            "room_type": True,
            "number_of_reviews": ":,.0f",
            "review_count_display": False,
            "review_scores_rating": ":.2f",
            "is_reliable_review": True,
        },
        opacity=0.45,
    )
    fig.add_vline(
        x=5,
        line_color="#6B7C90",
        line_dash="dash",
        annotation_text="Reliable review threshold",
        annotation_position="top right",
    )
    fig.add_hline(
        y=median_score,
        line_color="#BF6C32",
        line_dash="dot",
        annotation_text=f"Median {median_score:.2f}",
        annotation_position="bottom right",
    )
    fig.update_traces(marker=dict(size=8))
    fig.update_layout(
        title="Review Score vs Review Evidence",
        title_font=dict(size=18, color="#0F2742"),
        title_x=0.0,
        xaxis_title="Number of reviews",
        yaxis_title="Review score",
        height=360,
        margin=dict(l=0, r=0, t=72, b=52),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0),
    )
    fig.update_yaxes(range=[0, 5])
    return fig


def _build_reliable_review_coverage_by_host_size(host_view: pd.DataFrame) -> go.Figure:
    if host_view.empty:
        return go.Figure()

    summary = (
        host_view.groupby("host_size_group", as_index=False)
        .agg(
            total_listings=("listing_id", "nunique"),
            reliable_listings=("is_reliable_review", "sum"),
        )
    )
    summary["reliable_review_coverage"] = (
        summary["reliable_listings"] / summary["total_listings"].replace(0, pd.NA)
    )
    summary["host_size_group"] = pd.Categorical(
        summary["host_size_group"],
        categories=["Solo", "Small", "Medium", "Large", "Unknown"],
        ordered=True,
    )
    summary = summary.sort_values("host_size_group")
    summary = summary[summary["total_listings"] > 0]
    if summary.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_bar(
        x=summary["host_size_group"],
        y=summary["reliable_review_coverage"],
        text=summary["reliable_review_coverage"].map(lambda value: f"{value:.1%}"),
        textposition="outside",
        marker_color="#0F2742",
        customdata=summary[["reliable_listings", "total_listings"]].values,
        hovertemplate=(
            "Host size: %{x}<br>"
            "Reliable review coverage: %{y:.1%}<br>"
            "Reliable listings: %{customdata[0]:,.0f}<br>"
            "Total listings: %{customdata[1]:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        title="Reliable Review Coverage by Host Size",
        title_font=dict(size=18, color="#0F2742"),
        title_x=0.0,
        xaxis_title="Host size",
        yaxis_title="Reliable review coverage",
        height=360,
        margin=dict(l=0, r=0, t=56, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return fig


def _build_host_benchmark_table(host_view: pd.DataFrame) -> pd.DataFrame:
    reliable_view = host_view[host_view["is_reliable_review"]].copy()
    if reliable_view.empty:
        return pd.DataFrame()

    host_flags = (
        host_view.sort_values(["host_id", "listing_id"])
        .drop_duplicates("host_id")
        .loc[:, ["host_id", "host_name", "host_is_superhost", "host_identity_verified"]]
    )
    summary = (
        host_view.groupby("host_id", as_index=False)
        .agg(
            listings=("listing_id", "nunique"),
            neighbourhoods=("neighbourhood", "nunique"),
            total_reviews=("number_of_reviews", "sum"),
            median_response_rate=("host_response_rate", "median"),
            median_acceptance_rate=("host_acceptance_rate", "median"),
        )
        .merge(
            reliable_view.groupby("host_id", as_index=False).agg(
                reliable_listings=("listing_id", "nunique"),
                median_review_score=("review_scores_rating", "median"),
                avg_value_score=("review_scores_value", "mean"),
            ),
            on="host_id",
            how="inner",
        )
        .merge(host_flags, on="host_id", how="left")
    )
    summary["reliable_review_coverage"] = (
        summary["reliable_listings"] / summary["listings"].replace(0, pd.NA)
    )
    summary = summary.sort_values(
        ["reliable_listings", "median_review_score", "total_reviews"],
        ascending=[False, False, False],
    ).head(20)
    if summary.empty:
        return summary

    summary["host_is_superhost"] = summary["host_is_superhost"].fillna(False).map({True: "Yes", False: "No"})
    summary["host_identity_verified"] = summary["host_identity_verified"].fillna(False).map({True: "Yes", False: "No"})
    summary["reliable_review_coverage"] = summary["reliable_review_coverage"].map(_format_pct)
    summary["median_review_score"] = summary["median_review_score"].map(_format_score)
    summary["avg_value_score"] = summary["avg_value_score"].map(_format_score)
    summary["median_acceptance_rate"] = summary["median_acceptance_rate"].map(_format_pct)
    summary["median_response_rate"] = summary["median_response_rate"].map(_format_pct)
    return summary.rename(
        columns={
            "host_id": "Host ID",
            "host_name": "Host",
            "listings": "Listings",
            "neighbourhoods": "Neighbourhoods",
            "host_is_superhost": "Superhost",
            "host_identity_verified": "Verified",
            "median_review_score": "Median Review Score",
            "reliable_listings": "Reliable Listings",
            "reliable_review_coverage": "Reliable Review Coverage",
            "total_reviews": "Total Reviews",
            "median_response_rate": "Median Response Rate",
            "median_acceptance_rate": "Median Acceptance Rate",
            "avg_value_score": "Avg Value Score",
        }
    )[
        [
            "Host",
            "Host ID",
            "Superhost",
            "Verified",
            "Listings",
            "Reliable Listings",
            "Reliable Review Coverage",
            "Median Review Score",
            "Total Reviews",
            "Avg Value Score",
            "Median Acceptance Rate",
            "Median Response Rate",
            "Neighbourhoods",
        ]
    ]


def _build_review_watchlist_table(
    host_view: pd.DataFrame,
    review_reference_date: pd.Timestamp | None,
) -> pd.DataFrame:
    view = host_view.copy()
    if view.empty:
        return pd.DataFrame()

    low_review_score_threshold = 4.5
    low_dimension_score_threshold = 4.5
    low_acceptance_rate_threshold = 0.8
    recent_review_horizon_days = 180
    stale_review_cutoff = (
        review_reference_date - pd.Timedelta(days=recent_review_horizon_days)
        if pd.notna(review_reference_date)
        else pd.NaT
    )

    def build_watchlist_reason(row: pd.Series) -> str:
        reasons: list[str] = []
        reviews = row["number_of_reviews"] if pd.notna(row["number_of_reviews"]) else 0
        verified_value = row.get("host_identity_verified", False)
        is_verified = pd.notna(verified_value) and bool(verified_value)
        if (
            row["is_reliable_review"]
            and pd.notna(row["review_scores_rating"])
            and row["review_scores_rating"] < low_review_score_threshold
        ):
            reasons.append("Low Review Score")
        if reviews < 5:
            reasons.append("Insufficient Review Evidence")
        if (
            row["is_reliable_review"]
            and pd.notna(row["review_scores_value"])
            and row["review_scores_value"] < low_dimension_score_threshold
        ):
            reasons.append("Low Value Score")
        if (
            row["is_reliable_review"]
            and pd.notna(row["review_scores_cleanliness"])
            and row["review_scores_cleanliness"] < low_dimension_score_threshold
        ):
            reasons.append("Low Cleanliness Score")
        if not is_verified:
            reasons.append("Unverified Host")
        if pd.notna(row["host_acceptance_rate"]) and row["host_acceptance_rate"] < low_acceptance_rate_threshold:
            reasons.append("Low Acceptance Rate")
        if pd.notna(stale_review_cutoff) and pd.notna(row["last_review_date"]) and row["last_review_date"] < stale_review_cutoff:
            reasons.append("No Recent Reviews")
        return "; ".join(reasons)

    view["watchlist_reason"] = view.apply(build_watchlist_reason, axis=1)
    view = view[view["watchlist_reason"] != ""].copy()
    if view.empty:
        return view

    view = view.sort_values(
        ["is_reliable_review", "review_scores_rating", "number_of_reviews", "host_acceptance_rate"],
        ascending=[False, True, True, True],
    ).head(20)
    view["host_is_superhost"] = view["host_is_superhost"].fillna(False).map({True: "Yes", False: "No"})
    view["host_identity_verified"] = view["host_identity_verified"].fillna(False).map({True: "Yes", False: "No"})
    view["last_review_date"] = pd.to_datetime(view["last_review_date"], errors="coerce").dt.date
    view["review_scores_rating"] = view["review_scores_rating"].map(_format_score)
    view["host_acceptance_rate"] = view["host_acceptance_rate"].map(_format_pct)
    return view.rename(
        columns={
            "listing_id": "Listing ID",
            "listing_name": "Listing",
            "host_name": "Host",
            "neighbourhood": "Neighbourhood",
            "room_type": "Room Type",
            "watchlist_reason": "Review Watchlist Reason",
            "review_scores_rating": "Review Score",
            "number_of_reviews": "Reviews",
            "host_acceptance_rate": "Acceptance Rate",
            "last_review_date": "Last Review Date",
            "host_is_superhost": "Superhost",
            "host_identity_verified": "Verified",
        }
    )[
        [
            "Listing",
            "Review Watchlist Reason",
            "Neighbourhood",
            "Room Type",
            "Review Score",
            "Reviews",
            "Last Review Date",
            "Acceptance Rate",
            "Host",
            "Superhost",
            "Verified",
            "Listing ID",
        ]
    ]


def render_host_review_quality() -> None:
    try:
        host_quality = load_host_quality_dataset()
        review_recency = load_listing_review_recency_dataset()
    except Exception as exc:  # pragma: no cover
        st.error(f"Cannot load host & review quality data from Gold layer.\n\nError: {exc}")
        return

    if host_quality.empty:
        st.warning("Host quality dataset is empty.")
        return

    host_quality = host_quality.copy()
    if "host_size_group" not in host_quality.columns:
        host_quality["host_size_group"] = host_quality["host_total_listings_count"].apply(
            _assign_host_size_group
        )
    if "is_reliable_review" not in host_quality.columns:
        host_quality["is_reliable_review"] = (
            host_quality["review_scores_rating"].notna()
            & (host_quality["number_of_reviews"] >= 5)
        )

    global_review_reference_date = review_recency["global_latest_review_date"].max()
    host_quality = host_quality.merge(
        review_recency.loc[
            :,
            [
                "listing_id",
                "last_review_date",
                "review_event_count",
                "comment_count",
                "has_any_comment",
                "days_since_last_review",
            ],
        ],
        on="listing_id",
        how="left",
    )

    filters = _render_filters(host_quality)
    host_view = _apply_filters(host_quality, filters)

    if host_view.empty:
        st.warning("No host or listing records match the current filter set.")
        return

    _render_kpis(host_view)

    row_1_left, row_1_right = two_column_layout([1.0, 1.0])
    with row_1_left:
        fig = _build_superhost_comparison(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("Not enough host-tier data to compare superhosts and non-superhosts.")
    with row_1_right:
        fig = _build_review_dimension_profile(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("Review dimension scores are not available in the current filtered view.")

    row_2_left, row_2_right = two_column_layout([1.0, 1.0])
    with row_2_left:
        fig = _build_host_size_operations(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("Not enough host-size data to compare acceptance risk.")
    with row_2_right:
        fig = _build_reliable_review_coverage_by_host_size(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("No reliable review coverage by host size is available under the current filters.")

    st.caption(
        "Thresholds are dashboard-defined: reliable review = at least 5 reviews and non-null rating; acceptance risk = acceptance rate below 80%; no recent reviews = last review older than 180 days relative to the latest review date in the dataset."
    )
    row_3_left, row_3_right = two_column_layout([1.0, 1.0])
    with row_3_left:
        fig = _build_review_quality_distribution(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("No listing review quality distribution is available under the current filters.")
    with row_3_right:
        fig = _build_review_score_vs_evidence(host_view)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True, config=DEFAULT_PLOTLY_CONFIG)
        else:
            st.info("No review score versus review evidence view is available under the current filters.")

    st.markdown("#### Host & Review Drill-down")
    st.caption(
        "Use this section for host- and listing-level drill-down after reviewing the summary charts. Review scores and host rates are snapshot-based indicators from the Gold layer."
    )
    benchmark_tab, watchlist_tab = st.tabs(["Top Quality Hosts", "Review Watchlist"])
    with benchmark_tab:
        benchmark = _build_host_benchmark_table(host_view)
        if benchmark.empty:
            st.info("No host benchmark rows are available for the current filtered view.")
        else:
            st.dataframe(benchmark, use_container_width=True, hide_index=True)
    with watchlist_tab:
        watchlist = _build_review_watchlist_table(host_view, global_review_reference_date)
        if watchlist.empty:
            st.info("No review watchlist rows are available for the current filtered view.")
        else:
            st.dataframe(watchlist, use_container_width=True, hide_index=True)
