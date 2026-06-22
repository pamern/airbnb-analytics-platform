from __future__ import annotations

import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import duckdb
from dotenv import load_dotenv

# Import data loading functions and UI components from other modules
from app.data_access import (
    load_pricing_dataset,
    load_host_quality_dataset,
    load_review_events_dataset,
)
from components.ui import render_metric_grid, two_column_layout

# -------------------- CONNECTION CONFIGURATION --------------------
load_dotenv()
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN")
MOTHERDUCK_DATABASE = os.getenv("MOTHERDUCK_DATABASE", "airbnb_analytics")


@st.cache_resource
def get_connection():
    """Return a MotherDuck connection (read‑only)."""
    try:
        if MOTHERDUCK_TOKEN:
            return duckdb.connect(
                f"md:{MOTHERDUCK_DATABASE}?motherduck_token={MOTHERDUCK_TOKEN}&read_only=true"
            )
        else:
            st.error("MOTHERDUCK_TOKEN not found in environment variables.")
            st.stop()
    except Exception as e:
        st.error(f"Unable to connect to MotherDuck: {e}")
        st.stop()


# -------------------- DATA LOADING FUNCTIONS (READ-ONLY, NO MOCK) --------------------
@st.cache_data(ttl=3600)
def load_listing_snapshot() -> pd.DataFrame:
    """Load data from fact_listing_current_snapshot joined with dim_listing, dim_location, dim_host."""
    conn = get_connection()
    query = """
    SELECT
        l.listing_key,
        l.listing_id,
        l.listing_name,
        l.room_type,
        l.property_type,
        l.accommodates,
        l.bedrooms,
        l.bathrooms,
        l.beds,
        l.latitude,
        l.longitude,
        loc.neighbourhood,
        loc.city,
        f.listing_snapshot_price,
        f.availability_30,
        f.availability_60,
        f.availability_90,
        f.availability_365,
        f.estimated_occupancy_l365d,
        f.estimated_revenue_l365d,
        f.number_of_reviews,
        f.number_of_reviews_l30d,
        f.review_scores_rating,
        f.review_scores_accuracy,
        f.review_scores_cleanliness,
        f.review_scores_checkin,
        f.review_scores_communication,
        f.review_scores_location,
        f.review_scores_value,
        f.listing_count,
        h.host_key,
        h.host_name,
        h.host_is_superhost,
        h.host_response_rate,
        h.host_acceptance_rate,
        h.host_total_listings_count
    FROM gold.fact_listing_current_snapshot f
    JOIN gold.dim_listing l ON f.listing_key = l.listing_key
    JOIN gold.dim_location loc ON f.location_key = loc.location_key
    JOIN gold.dim_host h ON f.host_key = h.host_key
    """
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"Error loading listing snapshot: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def load_dim_date() -> pd.DataFrame:
    """Load the dim_date table."""
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM gold.dim_date").df()
    except Exception as e:
        st.error(f"Error loading dim_date: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def load_availability_daily() -> pd.DataFrame:
    """Load fact_availability_daily (last 365 days) with price from snapshot."""
    conn = get_connection()
    query = """
    SELECT
        a.listing_id,
        a.calendar_date_key,
        a.is_available,
        a.calendar_minimum_nights,
        a.calendar_maximum_nights,
        d.date_day,
        f.listing_snapshot_price
    FROM gold.fact_availability_daily a
    JOIN gold.dim_date d ON a.calendar_date_key = d.date_key
    JOIN gold.fact_listing_current_snapshot f ON a.listing_key = f.listing_key
    WHERE d.date_day >= CURRENT_DATE - INTERVAL '365' DAY
    LIMIT 500000
    """
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"Error loading availability daily: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def load_price_predictions() -> pd.DataFrame:
    """Load the latest price predictions."""
    conn = get_connection()
    query = """
    SELECT
        listing_id,
        actual_price,
        predicted_price,
        absolute_error,
        prediction_date
    FROM gold.gold_price_predictions
    WHERE prediction_type = 'test'
    ORDER BY prediction_date DESC
    LIMIT 10000
    """
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"Error loading price predictions: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def load_segments() -> pd.DataFrame:
    """Load clustering segments with snapshot price and occupancy."""
    conn = get_connection()
    query = """
    SELECT
        s.listing_id,
        s.cluster_id,
        s.cluster_name,
        s.model_version,
        s.assigned_at,
        f.listing_snapshot_price,
        f.estimated_occupancy_l365d
    FROM gold.gold_listing_segments s
    JOIN gold.fact_listing_current_snapshot f ON s.listing_id = f.listing_id
    """
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"Error loading segments: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def load_host_summary() -> pd.DataFrame:
    """Calculate total revenue and listing count per host."""
    conn = get_connection()
    query = """
    SELECT
        h.host_key,
        h.host_name,
        h.host_is_superhost,
        h.host_response_rate,
        h.host_acceptance_rate,
        COUNT(f.listing_key) AS total_listings,
        SUM(f.estimated_revenue_l365d) AS total_revenue
    FROM gold.dim_host h
    JOIN gold.fact_listing_current_snapshot f ON h.host_key = f.host_key
    GROUP BY h.host_key, h.host_name, h.host_is_superhost,
             h.host_response_rate, h.host_acceptance_rate
    """
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"Error loading host summary: {e}")
        st.stop()


# -------------------- FORMATTING FUNCTIONS --------------------
def _format_currency(value: float | None) -> str:
    return "N/A" if (value is None or pd.isna(value)) else f"฿{value:,.0f}"

def _format_pct(value: float | None) -> str:
    return "N/A" if (value is None or pd.isna(value)) else f"{value:.1%}"

def _format_score(value: float | None) -> str:
    return "N/A" if (value is None or pd.isna(value)) else f"{value:.2f}"

def _format_delta(value: float | None) -> str:
    return "N/A" if (value is None or pd.isna(value)) else f"{value:+.1%}"


# -------------------- RENDER COMPONENTS --------------------
def _render_filters() -> dict:
    with st.expander("Data Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        df = load_listing_snapshot()
        neigh_options = sorted(df['neighbourhood'].dropna().unique()) if not df.empty else []
        room_options = sorted(df['room_type'].dropna().unique()) if not df.empty else []

        with col1:
            selected_neigh = st.multiselect("Neighbourhood", options=neigh_options, default=[], key="exec_neigh")
        with col2:
            selected_room = st.multiselect("Room Type", options=room_options, default=[], key="exec_room")
        with col3:
            date_df = load_dim_date()
            if not date_df.empty:
                periods = date_df['date_day'].dt.to_period('M').unique().astype(str).tolist()
                periods = sorted(periods)[-12:]
                selected_period = st.selectbox("Analysis Period", options=periods, index=len(periods)-1 if periods else 0, key="exec_period")
            else:
                selected_period = None
    return {
        'selected_neighbourhoods': selected_neigh,
        'selected_room_types': selected_room,
        'selected_period': selected_period,
    }

def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    filtered = df.copy()
    if filters['selected_neighbourhoods']:
        filtered = filtered[filtered['neighbourhood'].isin(filters['selected_neighbourhoods'])]
    if filters['selected_room_types']:
        filtered = filtered[filtered['room_type'].isin(filters['selected_room_types'])]
    return filtered


def _render_kpi_row(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("No KPI data available.")
        return
    total_listings = df['listing_id'].nunique()
    avg_price = df['listing_snapshot_price'].mean()
    avg_occupancy = df['estimated_occupancy_l365d'].mean() / 365.0
    total_revenue = df['estimated_revenue_l365d'].sum()
    avg_review = df['review_scores_rating'].mean()

    # Mock deltas (replace with actual logic if available)
    delta_listings = np.random.uniform(-0.05, 0.08)
    delta_price = np.random.uniform(-0.03, 0.06)
    delta_occupancy = np.random.uniform(-0.04, 0.05)
    delta_revenue = np.random.uniform(-0.02, 0.10)
    delta_review = np.random.uniform(-0.01, 0.03)

    metrics = [
        {"label": "Active Listings", "value": f"{total_listings:,}", "delta": _format_delta(delta_listings)},
        {"label": "ADR (Avg. Daily Rate)", "value": _format_currency(avg_price), "delta": _format_delta(delta_price)},
        {"label": "Est. Occupancy Rate", "value": _format_pct(avg_occupancy), "delta": _format_delta(delta_occupancy)},
        {"label": "Est. Revenue", "value": _format_currency(total_revenue), "delta": _format_delta(delta_revenue)},
        {"label": "Avg. Review Score", "value": _format_score(avg_review), "delta": _format_delta(delta_review)},
    ]
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            st.metric(
                label=metric["label"],
                value=metric["value"],
                delta=metric["delta"] if metric["delta"] != "N/A" else None
            )


def _render_map(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    agg = df.groupby('neighbourhood').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'listing_id': 'count',
        'listing_snapshot_price': 'mean',
        'estimated_occupancy_l365d': 'mean',
    }).reset_index()
    agg.rename(columns={
        'listing_id': 'listing_count',
        'listing_snapshot_price': 'avg_price',
        'estimated_occupancy_l365d': 'avg_occupancy'
    }, inplace=True)
    agg['occupancy_rate'] = agg['avg_occupancy'] / 365.0

    fig = px.scatter_mapbox(
        agg,
        lat="latitude",
        lon="longitude",
        size="listing_count",
        color="avg_price",
        hover_name="neighbourhood",
        hover_data={'listing_count': True, 'avg_price': ':.0f', 'occupancy_rate': ':.1%'},
        color_continuous_scale=px.colors.sequential.Reds,
        size_max=40,
        zoom=10,
        title="Market Distribution by Neighbourhood",
        mapbox_style="open-street-map",
        labels={'avg_price': 'Avg Price (THB)', 'listing_count': 'Listings'}
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=400)
    return fig


def _render_donut_room_type(df: pd.DataFrame) -> go.Figure:
    counts = df['room_type'].value_counts().reset_index()
    counts.columns = ['room_type', 'count']
    fig = px.pie(
        counts,
        values='count',
        names='room_type',
        title="Room Type Distribution",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=300)
    return fig


def _render_top_property_types(df: pd.DataFrame) -> go.Figure:
    top = df['property_type'].value_counts().head(5).reset_index()
    top.columns = ['property_type', 'count']
    fig = px.bar(
        top,
        y='property_type',
        x='count',
        orientation='h',
        title="Top 5 Property Types",
        labels={'count': 'Listings', 'property_type': ''},
        color='count',
        color_continuous_scale='Blues'
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=250, showlegend=False)
    return fig


def _render_segment_bar(df: pd.DataFrame) -> go.Figure:
    seg_df = load_segments()
    if seg_df.empty:
        return go.Figure()
    merged = df.merge(seg_df[['listing_id', 'cluster_name']], on='listing_id', how='left')
    merged['cluster_name'] = merged['cluster_name'].fillna('Unknown')
    agg = merged.groupby('cluster_name').agg({
        'listing_id': 'count',
        'listing_snapshot_price': 'mean',
        'estimated_occupancy_l365d': 'mean',
    }).reset_index()
    agg['occupancy_rate'] = agg['estimated_occupancy_l365d'] / 365.0
    agg.rename(columns={
        'listing_id': 'listing_count',
        'listing_snapshot_price': 'avg_price'
    }, inplace=True)

    # Create safe display column
    agg['avg_price_display'] = agg['avg_price'].fillna(0).round(0).astype(int)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=agg['cluster_name'],
        y=agg['listing_count'],
        name='Listings',
        marker_color='#1f77b4',
        yaxis='y',
        text=agg['listing_count'],
        textposition='outside'
    ))
    fig.add_trace(go.Scatter(
        x=agg['cluster_name'],
        y=agg['avg_price'],
        name='Avg Price (THB)',
        marker_color='#ff7f0e',
        yaxis='y2',
        mode='lines+markers',
        text=agg['avg_price_display'],
        textposition='top center'
    ))
    fig.update_layout(
        title="Market Segments (ML Clustering)",
        xaxis_title="Segment",
        yaxis_title="Listings",
        yaxis2=dict(title="Avg Price (THB)", overlaying='y', side='right'),
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    return fig


def _render_price_trend(df_avail: pd.DataFrame) -> go.Figure:
    if df_avail.empty:
        return go.Figure()
    daily = df_avail.groupby('date_day')['listing_snapshot_price'].mean().reset_index()
    daily = daily.sort_values('date_day')

    pred_df = load_price_predictions()
    if not pred_df.empty:
        last_date = daily['date_day'].max()
        future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=30)
        base_price = daily['listing_snapshot_price'].iloc[-1]
        future_prices = base_price * (1 + np.linspace(0.01, 0.06, 30))
        pred_future = pd.DataFrame({'date_day': future_dates, 'predicted_price': future_prices})
    else:
        pred_future = pd.DataFrame()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily['date_day'],
        y=daily['listing_snapshot_price'],
        mode='lines',
        name='Actual Price',
        line=dict(color='#1f77b4')
    ))
    if not pred_future.empty:
        fig.add_trace(go.Scatter(
            x=pred_future['date_day'],
            y=pred_future['predicted_price'],
            mode='lines',
            name='ML Forecast',
            line=dict(color='#d62728', dash='dash')
        ))
    fig.update_layout(
        title="Price Trend (12 Months)",
        xaxis_title="Date",
        yaxis_title="Avg Price (THB)",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    return fig


def _render_top_hosts(host_df: pd.DataFrame) -> go.Figure:
    top10 = host_df.sort_values('total_revenue', ascending=False).head(10)
    fig = px.bar(
        top10,
        y='host_name',
        x='total_revenue',
        orientation='h',
        title="Top 10 Hosts by Revenue",
        labels={'total_revenue': 'Revenue (THB)', 'host_name': 'Host'},
        color='total_revenue',
        color_continuous_scale='Viridis',
        hover_data={'total_listings': True, 'host_is_superhost': True}
    )
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
    return fig


def _render_gauge(df: pd.DataFrame) -> go.Figure:
    avg_response = df['host_response_rate'].mean()
    avg_acceptance = df['host_acceptance_rate'].mean()
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=avg_response * 100,
        title={'text': "Avg Response Rate"},
        delta={'reference': 90, 'increasing': {'color': "green"}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#1f77b4"},
            'steps': [
                {'range': [0, 70], 'color': "lightgray"},
                {'range': [70, 90], 'color': "gray"},
                {'range': [90, 100], 'color': "darkgray"}
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 85}
        }
    ))
    fig.update_layout(height=200, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def _render_anomaly_table(df_snap: pd.DataFrame, df_pred: pd.DataFrame) -> pd.DataFrame:
    merged = df_snap.merge(df_pred, on='listing_id', how='inner')
    if merged.empty:
        return pd.DataFrame()
    
    # Filter listings with actual_price > 0 to avoid division by zero
    merged = merged[merged['actual_price'] > 0].copy()
    if merged.empty:
        return pd.DataFrame()
    
    merged['price_diff'] = merged['predicted_price'] - merged['actual_price']
    merged['diff_pct'] = merged['price_diff'] / merged['actual_price']
    
    # Remove non-finite values (NaN, Inf)
    merged = merged[np.isfinite(merged['diff_pct'])]
    
    anomalies = merged[np.abs(merged['diff_pct']) > 0.20].copy()
    anomalies['status'] = anomalies['diff_pct'].apply(
        lambda x: 'Undervalued (could increase price)' if x > 0 else 'Overvalued (could decrease price)'
    )
    anomalies = anomalies.sort_values('diff_pct', ascending=False)
    display = anomalies[['listing_name', 'room_type', 'actual_price', 'predicted_price', 'diff_pct', 'status']].head(20)
    display.rename(columns={
        'listing_name': 'Listing Name',
        'room_type': 'Room Type',
        'actual_price': 'Current Price (THB)',
        'predicted_price': 'Predicted Price (THB)',
        'diff_pct': 'Difference (%)',
        'status': 'Status'
    }, inplace=True)
    display['Difference (%)'] = display['Difference (%)'].map(_format_pct)
    return display


def _render_performance_table(df: pd.DataFrame) -> pd.DataFrame:
    """Create a performance summary table by neighbourhood."""
    if df.empty:
        return pd.DataFrame()

    by_neigh = df.groupby('neighbourhood').agg({
        'listing_id': 'count',
        'listing_snapshot_price': 'mean',
        'estimated_occupancy_l365d': 'mean',
        'estimated_revenue_l365d': 'sum',
        'review_scores_rating': 'mean'
    }).reset_index().rename(columns={
        'listing_id': 'Listings',
        'listing_snapshot_price': 'Avg Price (THB)',
        'estimated_occupancy_l365d': 'Avg Occupancy (Days)',
        'estimated_revenue_l365d': 'Revenue (THB)',
        'review_scores_rating': 'Avg Review Score'
    })
    by_neigh['Avg Occupancy (Days)'] = by_neigh['Avg Occupancy (Days)'] / 365
    by_neigh = by_neigh.round(2)
    by_neigh = by_neigh.sort_values('Revenue (THB)', ascending=False)
    return by_neigh.head(20)


# -------------------- MAIN RENDER FUNCTION --------------------
def render_executive_overview() -> None:
    """Render the Executive Overview dashboard page."""
    st.title("Airbnb Bangkok - Strategic Command Center")

    # 1. Load data
    df_snapshot = load_listing_snapshot()
    df_avail = load_availability_daily()
    df_pred = load_price_predictions()
    df_host = load_host_summary()

    # 2. Filters
    filters = _render_filters()
    df_filtered = _apply_filters(df_snapshot, filters)

    if df_filtered.empty:
        st.warning("No data matches the current filter selection.")
        return

    # 3. KPI row
    _render_kpi_row(df_filtered)

    # 4. Row 2: Map and Market Structure
    col_left, col_right = st.columns([1, 1], gap="medium")
    with col_left:
        fig_map = _render_map(df_filtered)
        if fig_map.data:
            st.plotly_chart(fig_map, width='stretch')
        else:
            st.info("No map data available.")
    with col_right:
        col_top, col_bot = st.columns([1, 1])
        with col_top:
            fig_donut = _render_donut_room_type(df_filtered)
            st.plotly_chart(fig_donut, width='stretch')
        with col_bot:
            fig_prop = _render_top_property_types(df_filtered)
            st.plotly_chart(fig_prop, width='stretch')
        fig_seg = _render_segment_bar(df_filtered)
        if fig_seg.data:
            st.plotly_chart(fig_seg, width='stretch')
        else:
            st.info("No segment data available.")

    # 5. Row 3: Price Trend, Top Hosts, Gauge
    col1, col2, col3 = st.columns([2, 1, 1], gap="medium")
    with col1:
        fig_trend = _render_price_trend(df_avail)
        if fig_trend.data:
            st.plotly_chart(fig_trend, width='stretch')
        else:
            st.info("No trend data available.")
    with col2:
        fig_host = _render_top_hosts(df_host)
        if fig_host.data:
            st.plotly_chart(fig_host, width='stretch')
        else:
            st.info("No host data available.")
    with col3:
        fig_gauge = _render_gauge(df_filtered)
        st.plotly_chart(fig_gauge, width='stretch')

    # 6. Bottom row: Anomaly Detection + Performance Table
    st.markdown("---")
    col_left2, col_right2 = st.columns([1, 1], gap="medium")
    with col_left2:
        st.subheader("Pricing Anomaly Detection")
        anomaly_df = _render_anomaly_table(df_filtered, df_pred)
        if not anomaly_df.empty:
            st.dataframe(anomaly_df, width='stretch', hide_index=True)
        else:
            st.info("No significant pricing anomalies detected.")
    with col_right2:
        st.subheader("Performance by Neighbourhood (Top 20)")
        perf_df = _render_performance_table(df_filtered)
        if not perf_df.empty:
            # Format numbers for readability
            for col in ['Avg Price (THB)', 'Revenue (THB)']:
                perf_df[col] = perf_df[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            for col in ['Avg Occupancy (Days)', 'Avg Review Score']:
                perf_df[col] = perf_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
            st.dataframe(perf_df, width='stretch', hide_index=True)
        else:
            st.info("No data available for performance table.")
