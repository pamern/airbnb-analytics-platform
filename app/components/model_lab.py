from __future__ import annotations

from typing import Any

import plotly.express as px
import streamlit as st

from components.data import (
    get_feature_selection_summary,
    get_price_model_charts,
    get_price_model_metadata,
    get_selected_features,
)
from components.model3_kmeans import render_model3_kmeans_page
from components.ui import format_number


def _render_model_pipeline() -> None:
    cols = st.columns(4)
    steps = [
        ("01", "Feature layer", "Đọc feature từ Gold/listing_features."),
        ("02", "Evaluate", "So sánh HGB, RandomForest và XGBoost."),
        ("03", "Select", "Chọn model theo RMSE, MAE, R2 và fit time."),
        ("04", "Serve", "Gắn artifact vào UI để predict và giải thích."),
    ]
    for col, (index, title, body) in zip(cols, steps, strict=True):
        with col:
            with st.container(border=True):
                st.caption(f"Step {index}")
                st.markdown(f"**{title}**")
                st.caption(body)


def _render_price_model_overview() -> None:
    metadata = get_price_model_metadata()
    selected_features = get_selected_features()
    summary = get_feature_selection_summary()

    st.markdown("### Price prediction")
    if not metadata:
        st.warning("Chưa tìm thấy metadata cho price model.")
        return

    best_metrics = metadata.get("best_model_metrics", {})
    metric_cols = st.columns(5)
    metric_cols[0].metric("Best model", metadata.get("best_model_name", "N/A"))
    metric_cols[1].metric("RMSE", format_number(best_metrics.get("rmse_mean")))
    metric_cols[2].metric("MAE", format_number(best_metrics.get("mae_mean")))
    metric_cols[3].metric("R2", format_number(best_metrics.get("r2_mean")))
    metric_cols[4].metric("Features", selected_features.get("selected_feature_count", "N/A"))

    artifact_ready = metadata.get("model_artifact_saved", False)
    artifact_label = "✅ Sẵn sàng" if artifact_ready else "⏳ Đang chờ artifact"
    st.info(
        f"**Tóm tắt lần chạy** — "
        f"Target: `{metadata.get('target', 'N/A')}` | "
        f"Train rows: `{metadata.get('train_rows', 'N/A')}` | "
        f"Test rows: `{metadata.get('test_rows', 'N/A')}` | "
        f"Artifact: {artifact_label}"
    )

    if not summary.empty:
        chart_data = summary.copy()
        chart_data["candidate"] = chart_data["model"] + " - " + chart_data["feature_set"]
        fig = px.bar(
            chart_data,
            x="candidate",
            y="rmse_mean",
            color="model",
            text="rmse_mean",
            color_discrete_sequence=["#0F2742", "#6B7C90", "#D8E0EA"],
            labels={"candidate": "Candidate", "rmse_mean": "RMSE"},
        )
        fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
        fig.update_layout(
            height=380,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_tickangle=-18,
            margin=dict(l=10, r=10, t=20, b=40),
        )
        st.plotly_chart(fig, width="stretch")

        with st.expander("Xem bảng đánh giá"):
            st.dataframe(
                summary[
                    [
                        "model",
                        "feature_set",
                        "mae_mean",
                        "rmse_mean",
                        "r2_mean",
                        "fit_time_mean",
                        "predict_time_mean",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )


def _render_artifact_gallery() -> None:
    chart_files = get_price_model_charts()
    if not chart_files:
        return

    st.markdown("### Model artifacts")
    left, right = st.columns([0.32, 0.68])
    with left:
        chart_names = {chart.name: chart for chart in chart_files}
        selected_chart = st.selectbox("Chart", list(chart_names))
        st.caption("Đọc từ ml/outputs/price_modeling/charts.")
    with right:
        st.image(str(chart_names[selected_chart]), width="stretch")


def _collect_prediction_payload() -> dict[str, Any]:
    with st.form("price_prediction_form"):
        st.markdown("#### Listing input")
        basic_a, basic_b, basic_c = st.columns(3)
        with basic_a:
            neighbourhood = st.text_input("Neighbourhood", value="Sukhumvit")
            room_type = st.selectbox(
                "Room type",
                ["Entire home/apt", "Private room", "Hotel room", "Shared room"],
            )
        with basic_b:
            property_base_group = st.selectbox(
                "Property group", ["Apartment", "House", "Condo", "Hotel", "Other"]
            )
            host_response_time = st.selectbox(
                "Host response time",
                ["within an hour", "within a few hours", "within a day", "a few days or more"],
            )
        with basic_c:
            has_reviews = st.toggle("Has reviews", value=True)
            amenities_count = st.number_input("Amenities count", 0, 200, 25)

        st.markdown("#### Capacity and policy")
        cap_a, cap_b, cap_c, cap_d = st.columns(4)
        with cap_a:
            accommodates = st.number_input("Accommodates", 1, 20, 2)
            bedrooms = st.number_input("Bedrooms", 0, 20, 1)
        with cap_b:
            bathrooms = st.number_input("Bathrooms", 0.0, 20.0, 1.0, step=0.5)
            beds = st.number_input("Beds", 0, 30, 1)
        with cap_c:
            minimum_nights = st.number_input("Minimum nights", 1, 365, 1)
            maximum_nights = st.number_input("Maximum nights", 1, 1125, 365)
        with cap_d:
            host_acceptance_rate = st.slider("Host acceptance rate", 0, 100, 90)
            host_response_rate = st.slider("Host response rate", 0, 100, 90)

        submitted = st.form_submit_button("Chạy prediction", width="stretch")

    payload = {
        "neighbourhood": neighbourhood,
        "room_type": room_type,
        "property_base_group": property_base_group,
        "host_response_time": host_response_time,
        "accommodates": accommodates,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "beds": beds,
        "minimum_nights": minimum_nights,
        "maximum_nights": maximum_nights,
        "amenities_count": amenities_count,
        "has_reviews": has_reviews,
        "host_acceptance_rate": host_acceptance_rate,
        "host_response_rate": host_response_rate,
    }
    return payload if submitted else {}


def _render_prediction_runner() -> None:
    metadata = get_price_model_metadata()
    selected_features = get_selected_features()

    st.markdown("### Run price model")
    if not metadata.get("model_artifact_saved", False):
        st.info(
            "Notebook hiện chưa lưu model artifact. Form này đã sẵn sàng để gắn inference "
            "khi có file model trong ml/outputs/price_modeling/models."
        )

    payload = _collect_prediction_payload()
    if payload:
        st.warning("Chưa có model artifact để predict thật. Đây là payload UI đã tạo.")
        st.json(payload)

    with st.expander("Selected features từ notebook"):
        st.write(selected_features.get("selected_features", []))


def _render_cluster_workspace() -> None:
    left, right = st.columns([1.25, 1])
    with left:
        st.info(
            "**Cluster workspace** — Chỗ cho KMeans/DBSCAN/segmentation. "
            "Sẽ hiển thị scatter/map, số cụm, silhouette score và mô tả từng segment."
        )
    with right:
        metric_cols = st.columns(2)
        metric_cols[0].metric("Cluster count", "TBD")
        metric_cols[1].metric("Silhouette", "TBD")
        st.metric("Primary segment", "TBD")


def _render_future_model_workspace() -> None:
    render_model3_kmeans_page()


def render_model_lab_page() -> None:
    _render_model_pipeline()
    st.divider()

    overview_tab, run_tab, cluster_tab, future_tab = st.tabs(
        ["Tổng quan", "Chạy dự báo", "Cluster", "Model 3"]
    )
    with overview_tab:
        _render_price_model_overview()
        _render_artifact_gallery()
    with run_tab:
        _render_prediction_runner()
    with cluster_tab:
        _render_cluster_workspace()
    with future_tab:
        _render_future_model_workspace()

