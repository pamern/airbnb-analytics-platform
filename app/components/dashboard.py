from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _render_kpi_row() -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Listings", "TBD", help="Tổng số listing từ Gold mart")
    c2.metric("Median price", "TBD", help="Giá trung vị theo neighbourhood")
    c3.metric("Review score", "TBD", help="Điểm đánh giá trung bình")
    c4.metric("Availability", "TBD", help="Lịch trống trung bình theo listing")


def _render_market_flow() -> None:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    fig = go.Figure()
    fig.add_bar(
        name="Median price",
        x=months,
        y=[2800, 3100, 2950, 3400, 3250, 3600, 3100, 2900],
        marker_color="#0F2742",
    )
    fig.add_bar(
        name="Availability %",
        x=months,
        y=[72, 68, 75, 61, 66, 58, 70, 74],
        marker_color="#6B7C90",
        yaxis="y2",
    )
    fig.update_layout(
        title="Market flow — price & availability trend",
        yaxis=dict(title="Median price (THB)"),
        yaxis2=dict(title="Availability (%)", overlaying="y", side="right", range=[0, 120]),
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=340,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("⚠️ Placeholder data — sẽ đọc từ Gold mart khi dbt mart sẵn sàng.")


def _render_listing_mix() -> None:
    fig = go.Figure(go.Pie(
        labels=["Entire home/apt", "Private room", "Hotel / Shared"],
        values=[62, 29, 9],
        marker_colors=["#0F2742", "#6B7C90", "#D8E0EA"],
        hole=0.45,
        textinfo="label+percent",
    ))
    fig.update_layout(
        title="Listing mix",
        showlegend=False,
        height=340,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("⚠️ Placeholder data.")


def render_dashboard_page() -> None:
    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            st.selectbox("Layer", ["Gold mart", "Silver", "Bronze"], key="filter_layer")
        with fc2:
            st.selectbox("Market", ["Bangkok", "Chiang Mai", "Phuket"], key="filter_market")
        with fc3:
            st.selectbox("Period", ["This month", "Last 3 months", "YTD"], key="filter_period")

    _render_kpi_row()
    st.write("")

    left, right = st.columns([1.65, 0.85])
    with left:
        _render_market_flow()
    with right:
        _render_listing_mix()

    st.write("")
    tc, qc = st.columns([1.35, 0.9])
    with tc:
        st.info(
            "**Gold mart table** — Bảng chi tiết filter theo neighbourhood, room type, "
            "price bucket và review band. Sẽ load từ dbt mart."
        )
    with qc:
        st.info(
            "**Data quality** — Missing value, duplicate, outlier và kết quả dbt tests."
        )
