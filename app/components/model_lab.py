"""Read-only Model Performance views for the Streamlit Model Lab."""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from services.model_performance_service import (
    get_cluster_assignments, get_cluster_pca_data, get_cluster_profiles,
    get_feature_importance, get_metric_trend, get_model_metrics,
    get_model_registry, get_model_runs, get_price_evaluation_predictions,
    get_shap_sample_artifact, load_price_shap_artifact,
)
from services.price_prediction_service import (
    get_active_price_champion, get_comparable_listings, get_price_candidates,
    get_price_input_features, get_price_input_options, get_price_model_metrics,
    predict_single_listing, set_price_champion, PRICE_INPUT_SCHEMA,
)
from services.segment_prediction_service import (
    SEGMENT_ONLY_INPUT_SCHEMA, MIN_SEGMENT_DISTRIBUTION_SIZE,
    get_active_segment_champion, get_cluster_price_distribution, get_cluster_profile,
    get_segment_input_features, get_selectable_segment_versions,
    predict_listing_segment, set_segmentation_champion,
)
from styles.design_tokens import DESIGN_TOKENS as T

MODEL_NAMES = {"Price Model": "price_model", "Segmentation Model": "segmentation_model"}
PRICE_METRICS = {"rmse": "RMSE", "mae": "MAE", "r2": "R²"}
SEGMENTATION_METRICS = {"silhouette_score": "Silhouette Score", "davies_bouldin_score": "Davies–Bouldin Score", "inertia": "Inertia"}


def _styles() -> None:
    st.markdown(f"""<style>
    .section-title{{color:{T['color_text_primary']};font-size:{T['font_size_lg']};font-weight:600;margin-top:{T['space_5']}}}
    .section-copy{{color:{T['color_text_muted']};font-size:{T['font_size_sm']};margin-bottom:{T['space_3']}}}
    .badge{{display:inline-block;border-radius:{T['radius_pill']};padding:2px 8px;margin:0 6px 6px 0;font-size:{T['font_size_xs']};font-weight:600;background:{T['color_primary_soft']};color:{T['color_primary']}}}
    </style>""", unsafe_allow_html=True)


def _render_metric(col, label: str, value: str) -> None:
    """Render a metric card that allows line wrapping and uses a uniform font size."""
    col.markdown(
        f"""
        <div style="display: flex; flex-direction: column; justify-content: flex-start; min-height: 80px; margin-bottom: 10px; padding: 2px 0;">
            <div style="font-size: 0.85rem; color: {T['color_text_muted']}; font-weight: 500; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.5px;">{escape(label)}</div>
            <div style="font-size: 1.5rem; font-weight: 600; color: {T['color_text_primary']}; word-wrap: break-word; word-break: break-all; white-space: normal; line-height: 1.2;">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _layout(fig: go.Figure, height: int = 330) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor=T["color_surface"], plot_bgcolor=T["color_surface"], font={"family": T["font_family"], "color": T["color_text_primary"]}, margin={"l": 20, "r": 20, "t": 40, "b": 20}, hoverlabel={"bgcolor": T["color_surface"], "font_color": T["color_text_primary"]}, legend={"orientation": "h", "y": 1.12})
    fig.update_xaxes(gridcolor=T["color_border"]); fig.update_yaxes(gridcolor=T["color_border"])
    return fig


def _section(title: str, copy: str) -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div><div class="section-copy">{escape(copy)}</div>', unsafe_allow_html=True)


def _error(error: str | None) -> bool:
    if not error:
        return False
    if "no shap sample" in error.lower() or "no shap sample artifact" in error.lower(): st.info("No SHAP sample artifact is available for this model version.")
    elif "does not exist" in error.lower() or "not available" in error.lower() or "not found" in error.lower(): st.info("This table or artifact is not available yet.")
    else: st.error("Database connection failed or the requested model data could not be loaded.")
    return True


def _number(value: object, digits: int = 3) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "N/A" if pd.isna(numeric) else f"{numeric:,.{digits}f}"


def _badge(value: object) -> str:
    return f'<span class="badge">{escape(str(value or "UNKNOWN").upper())}</span>'


def _filter_bar() -> dict[str, object]:
    cols = st.columns(5)
    model_type = cols[0].selectbox("Model", list(MODEL_NAMES), key="model_performance_model_type")
    model_name = MODEL_NAMES[model_type]
    registry, _ = get_model_registry(model_name)
    cols[1].selectbox("Stage", ["All", "CHAMPION", "CANDIDATE", "ARCHIVED"], key="model_performance_stage")
    stage = st.session_state["model_performance_stage"]
    versions = registry["model_version"].dropna().astype(str).drop_duplicates().tolist() if not registry.empty else []
    champion = _champion(registry)
    if champion is not None:
        champion_version = str(champion["model_version"])
        versions = [champion_version, *[version for version in versions if version != champion_version]]
    if not versions:
        versions = [""]
    version_key = "performance_model_version"
    if st.session_state.get(version_key) not in versions:
        st.session_state.pop(version_key, None)
    selected_version = cols[2].selectbox("Model Version", versions, key=version_key, format_func=lambda version: f"{version} — Champion" if champion is not None and version == str(champion["model_version"]) else version)
    runs, _ = get_model_runs(model_name, None, None)
    types = ["All"] + (runs["run_type"].dropna().astype(str).drop_duplicates().tolist() if not runs.empty else [])
    run_type = cols[3].selectbox("Run Type", types, key=f"model_performance_run_type_{model_name}")
    selected_dates = cols[4].date_input("Date Range", (date.today() - timedelta(days=90), date.today()), key="model_performance_dates")
    dates = tuple(selected_dates) if isinstance(selected_dates, tuple) else (selected_dates, selected_dates)
    return {"model_type": model_type, "model_name": model_name, "stage": stage, "version": selected_version or None, "run_type": None if run_type == "All" else run_type, "date_from": dates[0], "date_to": dates[-1]}


def _registry(model_name: str, stage: str) -> pd.DataFrame:
    values, error = get_model_registry(model_name)
    if _error(error): return pd.DataFrame()
    return values if stage == "All" else values[values["stage"].astype(str).str.upper().eq(stage)].copy()


def _champion(registry: pd.DataFrame) -> pd.Series | None:
    if registry.empty: return None
    values = registry[registry["stage"].astype(str).str.upper().eq("CHAMPION") & registry["is_active"].fillna(False)]
    return None if values.empty else values.iloc[0]


def _version(registry: pd.DataFrame, requested: str | None) -> str | None:
    if requested: return requested
    champion = _champion(registry)
    return str(champion["model_version"]) if champion is not None else (None if registry.empty else str(registry.iloc[0]["model_version"]))


def _metric(metrics: pd.DataFrame, key: str, version: str | None, test_only: bool = True) -> object:
    if metrics.empty:
        return None
    values = metrics.copy()
    if "model_version" in values.columns and version:
        values = values[values["model_version"].astype(str).eq(version)]
    if "dataset_split" in values.columns and test_only:
        values = values[values["dataset_split"].astype(str).str.upper().eq("TEST")]
    if "metric_name" in values.columns:
        values = values[values["metric_name"].astype(str).str.lower().eq(key)]
    if values.empty or "metric_value" not in values.columns:
        return None
    return values.iloc[0]["metric_value"]


def _tables(model_name: str, registry: pd.DataFrame, filters: dict[str, object]) -> None:
    left, right = st.columns(2)
    with left:
        _section("Model Registry", "Read-only registry records for the selected model.")
        if registry.empty: st.info("No registry records match the current filters.")
        else:
            st.markdown("".join(_badge(v) for v in registry["stage"].dropna().unique()), unsafe_allow_html=True)
            st.dataframe(registry[["model_version", "stage", "is_active", "created_at", "promoted_at", "promoted_by", "artifact_path"]], use_container_width=True, hide_index=True)
    with right:
        _section("Recent Runs", "The 10 most recent runs matching the current filters.")
        runs, error = get_model_runs(model_name, filters["date_from"], filters["date_to"])
        if _error(error): return
        if filters["version"]: runs = runs[runs["model_version"].astype(str).eq(str(filters["version"]))]
        if filters["run_type"]: runs = runs[runs["run_type"].astype(str).eq(str(filters["run_type"]))]
        if runs.empty: st.info("No runs match the current filters."); return
        runs = runs.head(10); st.markdown("".join(_badge(v) for v in runs["status"].dropna().unique()), unsafe_allow_html=True)
        st.dataframe(runs[["run_id", "run_type", "status", "started_at", "completed_at", "artifact_path"]], use_container_width=True, hide_index=True)
        for _, run in runs[runs["status"].astype(str).str.upper().eq("FAILED") & runs["error_message"].notna()].iterrows():
            with st.expander(f"Failure details: {run['run_id']}"): st.code(str(run["error_message"]))


def _prediction_frame(predictions: pd.DataFrame, scale: str) -> pd.DataFrame:
    frame = predictions.copy()
    frame["raw_residual"] = frame["predicted_price"] - frame["actual_price"]
    frame["actual_display"] = np.log1p(frame["actual_price"]) if scale == "Log Price" else frame["actual_price"]
    frame["predicted_display"] = np.log1p(frame["predicted_price"]) if scale == "Log Price" else frame["predicted_price"]
    return frame


def _display_limit(frame: pd.DataFrame, display_range: str) -> float | None:
    if display_range == "All": return None
    return float(pd.concat([frame["actual_display"], frame["predicted_display"]]).quantile(0.95 if display_range == "P95" else 0.99))


def _price_diagnostics(frame: pd.DataFrame) -> None:
    residual = frame["raw_residual"]
    cols = st.columns(3)
    cols[0].metric("Underprediction Rate", f"{(residual < 0).mean():.1%}")
    cols[1].metric("Median Residual", _number(residual.median()))
    cols[2].metric("P90 Absolute Error", _number(residual.abs().quantile(0.90)))


def _price_scatter_and_residual(predictions: pd.DataFrame, version: str | None) -> None:
    controls = st.columns(3)
    scale = controls[0].selectbox("Display Scale", ["Log Price", "Raw Price"], key="price_display_scale")
    display_range = controls[1].selectbox("Display Range", ["P95", "P99", "All"], index=1, key="price_display_range")
    residual_scale = controls[2].selectbox("Residual Scale", ["Raw Residual", "Log Residual"], key="price_residual_scale")
    frame = _prediction_frame(predictions, scale); limit = _display_limit(frame, display_range)
    visible = frame if limit is None else frame[(frame["actual_display"] <= limit) & (frame["predicted_display"] <= limit)]
    outside = len(frame) - len(visible)
    left, right = st.columns(2)
    with left:
        _section("Predicted vs Actual", "Display limits affect only the visible chart; all evaluation rows remain in diagnostics.")
        st.caption(f"Showing {len(visible):,} of {len(frame):,} points; {outside:,} outlier(s) are outside the display range.")
        labels = {"actual_display": f"Actual {'Log Price' if scale == 'Log Price' else 'Price'}", "predicted_display": f"Predicted {'Log Price' if scale == 'Log Price' else 'Price'}"}
        fig = px.scatter(visible, x="actual_display", y="predicted_display", hover_data=["listing_id", "actual_price", "predicted_price", "prediction_error", "model_version"], labels=labels, color_discrete_sequence=[T["chart_primary"]])
        maximum = limit if limit is not None else max(frame["actual_display"].max(), frame["predicted_display"].max())
        fig.add_trace(go.Scatter(x=[0, maximum], y=[0, maximum], mode="lines", name="y = x", line={"color": T["chart_reference"], "dash": "dash"}))
        st.plotly_chart(_layout(fig), use_container_width=True)
        high = frame[frame["actual_price"] >= frame["actual_price"].quantile(0.90)]
        if not high.empty and (high["raw_residual"] < 0).mean() > 0.5: st.warning("The model tends to underpredict extreme high-price listings.")
    with right:
        _section("Residual Distribution", "Negative residual means underprediction. Positive residual means overprediction.")
        residual = frame["raw_residual"] if residual_scale == "Raw Residual" else np.log1p(frame["predicted_price"]) - np.log1p(frame["actual_price"])
        hist_limit = residual.abs().quantile(0.99); visible_residual = residual[residual.abs() <= hist_limit]
        fig = px.histogram(x=visible_residual, nbins=35, labels={"x": residual_scale}, color_discrete_sequence=[T["chart_secondary"]])
        fig.add_vline(x=0, line_dash="dash", line_color=T["chart_reference"]); fig.add_vline(x=float(residual.median()), line_dash="dot", line_color=T["chart_danger"], annotation_text="Median")
        st.plotly_chart(_layout(fig), use_container_width=True)
        st.caption(f"Histogram displays the central 99% of residuals; metrics use all {len(residual):,} rows.")
    _price_diagnostics(frame)


def _error_by_band(predictions: pd.DataFrame) -> None:
    _section("Error by Price Band", "Quantile-based actual-price bands reveal where price error changes.")
    frame = predictions.copy(); frame["absolute_error"] = (frame["predicted_price"] - frame["actual_price"]).abs(); frame["underprediction"] = frame["predicted_price"] < frame["actual_price"]
    labels = ["Low", "Mid", "High", "Premium", "Extreme"]
    try: frame["price_band"] = pd.qcut(frame["actual_price"], q=5, labels=labels, duplicates="drop")
    except ValueError: st.info("Not enough distinct actual prices to create price bands."); return
    summary = frame.groupby("price_band", observed=True).agg(MAE=("absolute_error", "mean"), Median_Absolute_Error=("absolute_error", "median"), Underprediction_Rate=("underprediction", "mean"), Sample_Count=("listing_id", "size")).reset_index()
    fig = px.bar(summary, x="price_band", y="MAE", text="Sample_Count", color_discrete_sequence=[T["chart_primary"]]); st.plotly_chart(_layout(fig), use_container_width=True)
    st.dataframe(summary.assign(Underprediction_Rate=lambda x: x["Underprediction_Rate"].map("{:.1%}".format)), use_container_width=True, hide_index=True)


def _metric_trend(filters: dict[str, object]) -> None:
    _section("Metric Trend", "Metrics from successful runs, displayed at each run timestamp.")
    version = str(filters["version"]) if filters["version"] else None
    available, error = get_metric_trend("price_model", filters["date_from"], filters["date_to"], model_version=version)
    if _error(error) or available.empty:
        st.info("No successful metric history is available for this model version and dataset split."); return
    splits = available["dataset_split"].fillna("UNSPECIFIED").astype(str).unique().tolist()
    default_split = next((split for split in splits if split.lower() == "test"), splits[0])
    split_key = "performance_dataset_split"
    if st.session_state.get(split_key) not in splits: st.session_state.pop(split_key, None)
    selected_split = st.selectbox("Dataset Split", splits, index=splits.index(default_split), key=split_key)
    trend, error = get_metric_trend("price_model", filters["date_from"], filters["date_to"], model_version=version, dataset_split=None if selected_split == "UNSPECIFIED" else selected_split)
    if _error(error) or trend.empty:
        st.info("No successful metric history is available for this model version and dataset split."); return
    metric_names = sorted(trend["metric_name"].dropna().astype(str).unique().tolist())
    metric_key = "performance_metric_name"
    if st.session_state.get(metric_key) not in metric_names: st.session_state.pop(metric_key, None)
    selected_metric = st.selectbox("Metric", metric_names, key=metric_key)
    visible = trend[trend["metric_name"].astype(str).eq(selected_metric)]
    if visible.empty: st.info("No successful metric history is available for this model version and dataset split."); return
    title = f"{selected_metric.upper()} Trend — {version} — {selected_split}"
    if len(visible) == 1:
        st.plotly_chart(_layout(px.scatter(visible, x="started_at", y="metric_value", title=title, hover_data=["started_at", "model_version", "dataset_split"], color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
        st.caption("Only one successful metric point is available for this selection.")
    else:
        st.plotly_chart(_layout(px.line(visible, x="started_at", y="metric_value", title=title, markers=True, hover_data=["started_at", "model_version", "dataset_split"], color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)


def _normalise_shap(frame: pd.DataFrame, allowed: list[str]) -> pd.DataFrame:
    columns = {str(column).lower(): column for column in frame.columns}
    feature = columns.get("feature_name") or columns.get("source_feature")
    shap = columns.get("shap_value")
    value = columns.get("feature_value")
    if not feature or not shap: return pd.DataFrame()
    result = frame.rename(columns={feature: "feature_name", shap: "shap_value"}).copy()
    result["feature_value"] = result[value] if value else None
    # Persisted samples are long-form transformed SHAP rows; original-level
    # importance names do not match their one-hot transformed feature names.
    return result.dropna(subset=["shap_value"])


TOP_N_SHAP_FEATURES = 12


def _format_feature_label(name: str) -> str:
    replacements = {"categorical__": "", "numeric__": "", "neighbourhood_": "Neighbourhood: ", "property_base_group_": "Property: ", "host_response_time_": "Host response: "}
    label = str(name)
    for source, target in replacements.items():
        label = label.replace(source, target)
    label = label.replace("_", " ").strip().title()
    return label if len(label) <= 42 else label[:41].rstrip() + "…"


def _shap_impact_overview(shap: pd.DataFrame) -> None:
    """Render a compact global-importance bar chart and a readable SHAP beeswarm."""
    importance = (shap.groupby("feature_name", as_index=False)["shap_value"].agg(mean_abs_shap=lambda values: values.abs().mean()).sort_values("mean_abs_shap", ascending=False).head(TOP_N_SHAP_FEATURES))
    feature_order = importance["feature_name"].tolist()
    plot_data = shap[shap["feature_name"].isin(feature_order)].copy()
    plot_data["feature_label"] = plot_data["feature_name"].map(_format_feature_label)
    numeric_color = pd.to_numeric(plot_data["feature_value"], errors="coerce")
    has_numeric_color = numeric_color.notna().mean() >= 0.5
    if has_numeric_color:
        plot_data["numeric_feature_value"] = numeric_color
    feature_to_y = {feature: index for index, feature in enumerate(reversed(feature_order))}
    plot_data["y_position"] = plot_data["feature_name"].map(feature_to_y) + np.random.default_rng(42).normal(0, 0.10, len(plot_data))
    importance_tab, distribution_tab = st.tabs(["Global Importance", "Impact Distribution"])
    with importance_tab:
        bars = importance.assign(feature_label=importance["feature_name"].map(_format_feature_label)).sort_values("mean_abs_shap")
        figure = px.bar(bars, x="mean_abs_shap", y="feature_label", orientation="h", color_discrete_sequence=[T["chart_primary"]])
        figure.update_layout(showlegend=False, margin={"l": 220, "r": 40, "t": 20, "b": 50})
        st.plotly_chart(_layout(figure, max(360, 32 * len(feature_order))), use_container_width=True)
        st.caption("Larger mean absolute SHAP values indicate greater overall influence on predicted log-price.")
    with distribution_tab:
        marker: dict[str, object] = {"size": 6, "opacity": 0.65 if has_numeric_color else 0.60, "color": plot_data["numeric_feature_value"] if has_numeric_color else T["chart_primary"]}
        if has_numeric_color:
            marker.update({"colorscale": [[0.0, T["color_primary_soft"]], [1.0, T["chart_primary"]]], "showscale": True, "colorbar": {"title": "Feature value", "thickness": 12}})
        customdata = np.column_stack([plot_data["feature_name"], plot_data["feature_value"].astype(str)])
        figure = go.Figure(go.Scattergl(x=plot_data["shap_value"], y=plot_data["y_position"], mode="markers", marker=marker, customdata=customdata, hovertemplate="Feature: %{customdata[0]}<br>Feature value: %{customdata[1]}<br>SHAP value: %{x:.4f}<extra></extra>"))
        ordered = list(reversed(feature_order))
        figure.update_layout(height=max(480, 38 * len(feature_order)), margin={"l": 220, "r": 40, "t": 20, "b": 50}, showlegend=False, xaxis_title="SHAP value", yaxis_title=None, hovermode="closest")
        figure.update_yaxes(tickmode="array", tickvals=[feature_to_y[feature] for feature in ordered], ticktext=[_format_feature_label(feature) for feature in ordered], showgrid=True, gridcolor=T["color_border"])
        figure.update_xaxes(zeroline=True, zerolinewidth=1.5, zerolinecolor=T["color_text_muted"], showgrid=True, gridcolor=T["color_border"])
        st.plotly_chart(_layout(figure, max(480, 38 * len(feature_order))), use_container_width=True)
        st.caption("Positive SHAP values increase predicted log-price; negative values decrease it.")


def _shap_views(version: str | None) -> None:
    importance, importance_error = get_feature_importance(version)
    _section("Global SHAP Feature Importance", "Mean absolute SHAP value on the evaluation sample. SHAP values explain predictions on the log-price scale.")
    if _error(importance_error): return
    registry, registry_error = get_model_registry("price_model")
    selected = registry[registry["model_version"].astype(str).eq(str(version))] if not registry.empty and version else pd.DataFrame()
    artifact, artifact_load_error = (None, "No SHAP artifact is available for this model version.") if selected.empty else load_price_shap_artifact(str(version), str(selected.iloc[0]["artifact_path"]))
    if artifact is not None:
        top = pd.DataFrame({"feature_name": artifact.feature_names, "importance_value": np.nanmean(np.abs(artifact.shap_values), axis=0)}).sort_values("importance_value", ascending=False).head(20)
    else:
        if importance.empty: st.info(artifact_load_error or "No SHAP feature importance is available for this model version."); return
        top = importance.head(15)
    st.plotly_chart(_layout(px.bar(top.sort_values("importance_value"), x="importance_value", y="feature_name", orientation="h", color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
    raw, artifact_error = get_shap_sample_artifact(version)
    _section("SHAP Impact Overview", "Mean absolute SHAP measures average contribution magnitude; larger values indicate greater overall influence on predicted log-price.")
    if _error(artifact_error): return
    if artifact is not None and artifact.feature_values is None:
        st.caption("Feature values are unavailable in this artifact, so only global importance is shown.")
        return
    shap = _normalise_shap(raw, top["feature_name"].astype(str).tolist())
    if shap.empty: st.info("The SHAP sample artifact does not contain the fields needed for impact views."); return
    _shap_impact_overview(shap)
    features = shap["feature_name"].drop_duplicates().tolist(); selected = st.selectbox("Feature to explain", features, key="shap_dependence_feature")
    subset = shap[shap["feature_name"].eq(selected)].copy(); values = pd.to_numeric(subset["feature_value"], errors="coerce")
    _section("SHAP Dependence Plot", "Relationship between source feature values and SHAP impact on the log-price prediction.")
    if values.notna().mean() > 0.8:
        fig = px.scatter(subset.assign(feature_value_numeric=values), x="feature_value_numeric", y="shap_value", color_discrete_sequence=[T["chart_primary"]]); fig.add_hline(y=0, line_color=T["chart_reference"], line_dash="dash"); st.plotly_chart(_layout(fig), use_container_width=True)
    else:
        grouped = subset.groupby("feature_value", dropna=False).agg(Mean_SHAP=("shap_value", "mean"), Median_SHAP=("shap_value", "median"), Sample_Count=("shap_value", "size")).reset_index(); st.dataframe(grouped, use_container_width=True, hide_index=True)
    summary = shap.groupby("feature_name").agg(**{"Mean |SHAP|": ("shap_value", lambda series: series.abs().mean()), "Mean SHAP": ("shap_value", "mean"), "Positive Impact Rate": ("shap_value", lambda series: (series > 0).mean()), "Negative Impact Rate": ("shap_value", lambda series: (series < 0).mean()), "Sample Count": ("shap_value", "size")}).reset_index().sort_values("Mean |SHAP|", ascending=False)
    _section("SHAP Direction Summary", "Ranked by Mean |SHAP|. All SHAP values are on the log-price scale.")
    st.dataframe(summary, use_container_width=True, hide_index=True)


def _price_model(filters: dict[str, object]) -> None:
    registry = _registry("price_model", str(filters["stage"])); version = _version(registry, filters["version"]); current = {**filters, "version": version}; champion = _champion(registry)
    metrics, metric_error = get_model_metrics("price_model", version); cols = st.columns(5)
    _render_metric(cols[0], "Active Champion", str(champion["model_version"]) if champion is not None else "No Champion")
    for col, (key, label) in zip(cols[1:4], PRICE_METRICS.items(), strict=True): _render_metric(col, f"{label} — TEST", _number(_metric(metrics, key, version)))
    _render_metric(cols[4], "Model Version", version or "N/A")
    if champion is None: st.warning("No active Price Model Champion is available.")
    _error(metric_error)
    predictions, prediction_error = get_price_evaluation_predictions(version)
    if not _error(prediction_error):
        if predictions.empty: st.info("No evaluation predictions are available for this model version.")
        else: _price_scatter_and_residual(predictions, version); _error_by_band(predictions)
    _shap_views(version); _metric_trend(current); _tables("price_model", registry, current)
    _promotion_controls()


@st.cache_data(ttl=300, show_spinner=False)
def _pca_projection(frame: pd.DataFrame) -> tuple[pd.DataFrame, tuple[float, float], str | None]:
    if frame.empty: return pd.DataFrame(), (0.0, 0.0), "No assignment-feature rows are available."
    frame = frame.head(2500).copy(); feature_columns = [column for column in frame if column.startswith("feature__")]
    if not feature_columns: return pd.DataFrame(), (0.0, 0.0), "No clustering feature columns are available."
    values = frame[feature_columns]; numeric = values.select_dtypes(include="number").columns.tolist(); categorical = [column for column in values if column not in numeric]
    transformers = []
    if numeric: transformers.append(("numeric", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric))
    if categorical: transformers.append(("categorical", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), categorical))
    if not transformers: return pd.DataFrame(), (0.0, 0.0), "No usable numeric or categorical clustering features are available."
    try:
        transformed = ColumnTransformer(transformers).fit_transform(values)
        coordinates = PCA(n_components=2, random_state=42).fit_transform(transformed.toarray() if hasattr(transformed, "toarray") else transformed)
        frame["PCA Component 1"], frame["PCA Component 2"] = coordinates[:, 0], coordinates[:, 1]
        variance = PCA(n_components=2, random_state=42).fit(transformed.toarray() if hasattr(transformed, "toarray") else transformed).explained_variance_ratio_
        return frame, (float(variance[0]), float(variance[1])), None
    except Exception:
        return pd.DataFrame(), (0.0, 0.0), "PCA visualization could not be computed from the available feature data."


def _segmentation_model(filters: dict[str, object]) -> None:
    registry = _registry("segmentation_model", str(filters["stage"])); version = _version(registry, filters["version"]); current = {**filters, "version": version}; champion = _champion(registry)
    metrics, metric_error = get_model_metrics("segmentation_model", version); profiles, profile_error = get_cluster_profiles(version); cols = st.columns(5)
    _render_metric(cols[0], "Active Champion", str(champion["model_version"]) if champion is not None else "No Champion")
    for col, (key, label) in zip(cols[1:4], SEGMENTATION_METRICS.items(), strict=True): _render_metric(col, label, _number(_metric(metrics, key, version, test_only=False)))
    _render_metric(cols[4], "Number of Clusters", _number(profiles["cluster_id"].nunique(), 0) if "cluster_id" in profiles else "N/A")
    if champion is None: st.warning("No active Segmentation Model Champion is available.")
    _error(metric_error); _error(profile_error)
    _section("PCA Cluster Projection", "PCA is used only for two-dimensional visualization. Cluster assignments come from the persisted KMeans model.")
    pca_source, pca_error = get_cluster_pca_data(version)
    if not _error(pca_error):
        projection, variance, projection_error = _pca_projection(pca_source)
        if _error(projection_error): pass
        elif projection.empty: st.info("No PCA projection data is available for this model version.")
        else:
            st.caption(f"Explained variance PC1: {variance[0]:.1%} · PC2: {variance[1]:.1%} · displaying up to 2,500 listings.")
            hover = [column for column in ("listing_id", "cluster_id", "cluster_name", "distance_to_centroid") if column in projection]
            st.plotly_chart(_layout(px.scatter(projection, x="PCA Component 1", y="PCA Component 2", color="cluster_id", hover_data=hover, color_discrete_sequence=[T["chart_primary"], T["chart_secondary"], T["chart_success"], T["chart_danger"], T["color_info"]])), use_container_width=True)
    assignments, assignment_error = get_cluster_assignments(version); trend, trend_error = get_metric_trend("segmentation_model", current["date_from"], current["date_to"], model_version=version); left, right = st.columns(2)
    with left:
        _section("Cluster Distribution", "Listing counts by cluster for the selected model version.")
        if not _error(assignment_error) and not assignments.empty: st.plotly_chart(_layout(px.bar(assignments, x="cluster_id", y="listing_count", color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
        elif not assignment_error: st.info("No cluster assignments are available for this model version.")
    with right:
        _section("Segmentation Metric Trend", "Metrics from successful segmentation runs.")
        if not _error(trend_error) and not trend.empty:
            metric_names = sorted(trend["metric_name"].dropna().astype(str).unique().tolist())
            preferred = next((metric for metric in ("silhouette_score", "davies_bouldin_score", "calinski_harabasz_score", "inertia") if metric in metric_names), metric_names[0])
            if st.session_state.get("segmentation_metric_name") not in metric_names: st.session_state.pop("segmentation_metric_name", None)
            selected_metric = st.selectbox("Segmentation Metric", metric_names, index=metric_names.index(preferred), key="segmentation_metric_name")
            visible = trend[trend["metric_name"].astype(str).eq(selected_metric)]
            title = f"{selected_metric.replace('_', ' ').title()} Trend — {version}"
            if len(visible) == 1:
                st.plotly_chart(_layout(px.scatter(visible, x="started_at", y="metric_value", title=title, color_discrete_sequence=[T["chart_primary"]])), use_container_width=True); st.caption("Only one successful run is available for this model version.")
            else: st.plotly_chart(_layout(px.line(visible, x="started_at", y="metric_value", title=title, markers=True, color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
    _section("Cluster Profiles", "Available profile fields are read directly from the Gold table.")
    if not _error(profile_error): st.dataframe(profiles, use_container_width=True, hide_index=True) if not profiles.empty else st.info("No cluster profiles are available for this model version.")
    _segmentation_promotion_controls(champion)
    _tables("segmentation_model", registry, current)


def _performance() -> None:
    _styles(); filters = _filter_bar()
    if filters["model_type"] == "Price Model": _price_model(filters)
    else: _segmentation_model(filters)


def _prediction_inputs(features: list[str], segment_features: list[str]) -> tuple[dict[str, object], bool, bool]:
    """Render the active Champion's raw feature schema in three balanced columns."""
    options, options_error = get_price_input_options(features)
    if options_error:
        st.info("Current categorical values could not be loaded from the feature table.")
    with st.form("price_prediction_form", clear_on_submit=True):
        st.markdown("#### Input Information")
        st.caption("Only raw fields required by the active Price Model Champion are shown.")
        values: dict[str, object] = {}
        groups = (
            ("Basic Information", "basic"),
            ("Review and Availability Information", "review"),
            ("Host Information and Policy", "host"),
        )
        columns = st.columns(3, gap="large")
        predict_pressed = False
        for column, (heading, group) in zip(columns, groups, strict=True):
            with column:
                st.markdown(f"**{heading}**")
                for name in features:
                    spec = PRICE_INPUT_SCHEMA[name]
                    if spec["group"] != group:
                        continue
                    label = str(spec["label"])
                    if spec["kind"] == "categorical":
                        choices = options.get(name, [])
                        if choices:
                            if name == "property_base_group":
                                values["property_type"] = st.selectbox("Property Type", choices, key="price_input_property_type")
                            else:
                                values[name] = st.selectbox(label, choices, key=f"price_input_{name}")
                        else:
                            st.caption(f"{label}: no Gold-table values available")
                    elif spec["kind"] == "integer":
                        values[name] = st.number_input(label, min_value=int(spec["min"]), max_value=int(spec["max"]), value=int(spec["default"]), step=1, key=f"price_input_{name}")
                    else:
                        values[name] = st.number_input(label, min_value=float(spec["min"]), max_value=float(spec["max"]), value=float(spec["default"]), step=float(spec["step"]), key=f"price_input_{name}")
                for name, spec in SEGMENT_ONLY_INPUT_SCHEMA.items():
                    if group != "basic" or name not in segment_features:
                        continue
                    if name == "beds":
                        values[name] = st.number_input(str(spec["label"]), min_value=float(spec["min"]), max_value=float(spec["max"]), value=float(spec["default"]), step=float(spec["step"]), key="segment_input_beds")
                    else:
                        values[name] = st.number_input(str(spec["label"]), min_value=int(spec["min"]), max_value=int(spec["max"]), value=int(spec["default"]), step=1, key="segment_input_amenities")
                if group == "host":
                    predict_pressed = st.form_submit_button("Predict Price", type="primary", use_container_width=True)
        reset_pressed = st.form_submit_button("Reset Inputs")
    return values, reset_pressed, predict_pressed


def _champion_card(champion: pd.Series | None) -> None:
    _section("Model Champion", "The active Price Model is the only model eligible for prediction.")
    if champion is None: st.error("No single active Price Model Champion is available. Prediction is disabled."); return
    metrics, error = get_price_model_metrics(str(champion["model_version"]))
    if _error(error): return
    cols = st.columns(3)
    _render_metric(cols[0], "Model Version", str(champion["model_version"]))
    _render_metric(cols[1], "Stage", str(champion["stage"]))
    _render_metric(cols[2], "Created At", str(champion.get("created_at", "N/A")))
    metric_cols = st.columns(3)
    for col, (key, label) in zip(metric_cols, PRICE_METRICS.items(), strict=True): _render_metric(col, label, _number(_metric(metrics, key, str(champion["model_version"]))))


def _segment_views(predicted_price: float, segment) -> None:
    _section("Predicted Segment", "Segment assignment comes from the active Segment Champion.")
    profile, profile_error = get_cluster_profile(segment.model_version, segment.cluster_id)
    distribution, distribution_error = get_cluster_price_distribution(segment.model_version, segment.cluster_id)
    if _error(profile_error) or profile.empty:
        st.info("Segment profile data is unavailable for this model version."); return
    row = profile.iloc[0]
    median = pd.to_numeric(pd.Series([row.get("median_price")]), errors="coerce").iloc[0]
    reference = pd.to_numeric(distribution.get("actual_price", pd.Series(dtype=float)), errors="coerce").dropna()
    p25, p75 = reference.quantile([.25, .75]) if len(reference) >= MIN_SEGMENT_DISTRIBUTION_SIZE else (np.nan, np.nan)
    position = "Within segment range" if pd.notna(p25) and p25 <= predicted_price <= p75 else "Below segment range" if pd.notna(p25) and predicted_price < p25 else "Above segment range" if pd.notna(p75) else "Segment range unavailable"
    cols = st.columns(4); cols[0].metric("Predicted Segment", segment.cluster_name); cols[1].metric("Segment Median", _number(median, 0)); cols[2].metric("Price Position", position); cols[3].metric("Difference vs Segment Median", "N/A" if pd.isna(median) or median == 0 else f"{(predicted_price - median) / median:+.1%}")
    if distribution_error or len(reference) < MIN_SEGMENT_DISTRIBUTION_SIZE:
        st.info("Not enough listings are available to estimate the segment price distribution.")
    else:
        _section("Price Position vs Segment", "Reference group: listings assigned to the predicted segment.")
        scale_mode = st.radio("Price scale", ["Trimmed", "Log", "Full"], horizontal=True, key="segment_price_scale_mode")
        lower_q, upper_q = reference.quantile(.01), reference.quantile(.99)
        display = reference.clip(lower=lower_q, upper=upper_q) if scale_mode == "Trimmed" else reference
        predicted_display = min(max(predicted_price, lower_q), upper_q) if scale_mode == "Trimmed" else predicted_price
        fig = go.Figure(go.Box(x=display, orientation="h", name="Predicted Segment", marker_color=T["chart_primary"]))
        annotation = "Predicted price"
        if scale_mode == "Trimmed" and predicted_price > upper_q: annotation = "Predicted price above display range"
        if scale_mode == "Trimmed" and predicted_price < lower_q: annotation = "Predicted price below display range"
        fig.add_vline(x=predicted_display, line_color=T["chart_danger"], line_width=2, annotation_text=annotation, annotation_position="top right")
        fig.add_vline(x=float(reference.median()), line_color=T["chart_reference"], line_dash="dash", annotation_text="Segment median", annotation_position="bottom right")
        if scale_mode == "Log": fig.update_xaxes(type="log")
        st.plotly_chart(_layout(fig, 220), use_container_width=True)
        if scale_mode == "Trimmed": st.caption("Display trimmed to the 1st–99th percentile; summary statistics use the full segment distribution.")
        elif scale_mode == "Log": st.caption("Log scale is used to make the long-tailed segment price distribution easier to inspect.")
        else: st.caption("Extreme listings may compress the main price distribution.")
        st.caption(f"Segment listings: {len(reference):,} · Median: {_number(reference.median(), 0)} · P25–P75: {_number(reference.quantile(.25), 0)}–{_number(reference.quantile(.75), 0)} · Max: {_number(reference.max(), 0)}")
    _section("Segment Profile", "Profile values are read from the persisted cluster profile table.")
    st.dataframe(profile, use_container_width=True, hide_index=True)


def _promotion_controls() -> None:
    candidates, error = get_price_candidates()
    if _error(error): return
    _section("Champion Management", "Promotion is explicit and affects only the Price Model registry.")
    if candidates.empty: st.info("Candidate list is empty."); return
    candidate = st.selectbox("Select Candidate Version", candidates["model_version"].astype(str).tolist(), key="price_candidate_version")
    confirm = st.checkbox("The current Champion will be archived and the selected Candidate will become active.", key="price_promotion_confirmation")
    if st.button("Set as Champion", type="primary", disabled=not confirm, key="set_price_champion"):
        error = set_price_champion(candidate)
        if error: st.error(error)
        else: st.success(f"{candidate} is now the active Price Model Champion."); st.rerun()


def _segmentation_promotion_controls(champion: pd.Series | None) -> None:
    """Keep Segmentation Champion selection independent from Price Champion state."""
    selectable, error = get_selectable_segment_versions()
    if _error(error): return
    _section("Segmentation Champion Management", "Promote a Candidate or restore an Archived Segmentation Model version.")
    if selectable.empty:
        st.info("No Segmentation Candidate or Archived version is currently available.")
        return
    versions = selectable["model_version"].astype(str).tolist()
    selected_version = st.selectbox(
        "Select Segmentation Version",
        versions,
        format_func=lambda version: f"{version} — {selectable.loc[selectable['model_version'].astype(str).eq(version), 'stage'].iloc[0].title()}",
        key="segmentation_champion_version",
    )
    selected = selectable.loc[selectable["model_version"].astype(str).eq(selected_version)].iloc[0]
    action = "Restore" if str(selected["stage"]).strip().upper() == "ARCHIVED" else "Promote"
    current = str(champion["model_version"]) if champion is not None else "No active Champion"
    st.caption(f"Current Champion: {current} · Selected Stage: {str(selected['stage']).title()} · Action: {action}")
    if action == "Restore": st.warning("This will restore a previously archived Segmentation Model as the active Champion.")
    confirm = st.checkbox("I confirm the current Segmentation Champion will be archived.", key="segmentation_promotion_confirmation")
    if st.button(f"{action} as Segmentation Champion", type="primary", disabled=not confirm, key="set_segmentation_champion"):
        promotion_error = set_segmentation_champion(selected_version)
        if promotion_error: st.error(promotion_error)
        else:
            st.session_state.pop("price_prediction_result", None)
            st.success(f"{selected_version} is now the active Segmentation Model Champion.")
            st.rerun()


def _prediction_runner() -> None:
    champion, champion_error = get_active_price_champion()
    segment_champion, segment_champion_error = get_active_segment_champion()
    features, schema_error = get_price_input_features(champion)
    segment_features, _ = get_segment_input_features(segment_champion)
    _champion_card(champion)
    if champion_error: st.error(champion_error)
    if schema_error: st.error(schema_error); return
    inputs, reset, predict = _prediction_inputs(features, segment_features)
    if reset: st.session_state.pop("price_prediction_result", None); st.rerun()
    if predict and champion is not None:
        missing = [name for name in features if name not in inputs and not (name == "property_base_group" and "property_type" in inputs)]
        if missing: st.error("Complete the required fields before requesting a prediction.")
        else:
            price, error = predict_single_listing(inputs, champion)
            if error: st.error(error)
            else:
                segment_inputs = {**inputs, "minimum_nights_log": float(np.log1p(inputs["minimum_nights"]))}
                segment, segment_error = (predict_listing_segment(segment_inputs, segment_champion) if segment_champion is not None else (None, segment_champion_error))
                st.session_state["price_prediction_result"] = {"prediction": price, "segment": segment, "segment_error": segment_error, "inputs": inputs, "time": pd.Timestamp.now()}
    result = st.session_state.get("price_prediction_result")
    if result:
            _section("Prediction Result", "Estimated nightly price from the active Champion artifact.")
            prediction = result["prediction"]
            result_cols = st.columns(3)
            result_cols[0].metric("Predicted Nightly Price", _number(prediction.predicted_price, 2))
            interval = "Run the updated Price Model pipeline" if prediction.prediction_lower is None else f"{_number(prediction.prediction_lower, 0)} – {_number(prediction.prediction_upper, 0)}"
            result_cols[1].metric("90% Prediction Interval", interval)
            result_cols[2].metric("Prediction Reliability", prediction.reliability_level or "Not assessed")
            if prediction.target_coverage is not None: st.caption("The interval was calibrated using held-out Price Model data.")
            if prediction.reliability_reasons: st.caption(" ".join(prediction.reliability_reasons[:2]))
            if result.get("segment") is None:
                st.info("Segment prediction is unavailable for the active Segment Champion.")
            else:
                _segment_views(prediction.predicted_price, result["segment"])
            _section("Why this price?", "Local SHAP contributions are shown on the log-price scale, not as THB.")
            if prediction.local_shap is None: st.info("Local SHAP is unavailable for this artifact version.")
            else:
                local = prediction.local_shap.head(10).sort_values("shap_value")
                chart = px.bar(local, x="shap_value", y="feature_name", orientation="h", color="direction", color_discrete_map={"INCREASE": T["chart_primary"], "DECREASE": T["chart_danger"], "NEUTRAL": T["color_text_muted"]})
                chart.update_layout(showlegend=False, xaxis_title="SHAP contribution (log-price)", yaxis_title=None)
                st.plotly_chart(_layout(chart, max(300, 34 * len(local))), use_container_width=True)
                st.caption("Positive contributions increase predicted log-price; negative contributions decrease it.")
            history = st.session_state.setdefault("recent_price_predictions", []); history.insert(0, {"Time": result["time"], "Model Version": prediction.model_version, "Predicted Price": prediction.predicted_price, "Neighbourhood": result["inputs"].get("neighbourhood"), "Room Type": result["inputs"].get("room_type")})
            _section("Recent Predictions", "Session-only history; no predictions are written to the warehouse.")
            st.dataframe(pd.DataFrame(history[:10]), use_container_width=True, hide_index=True)



def render_model_lab_page() -> None:
    performance_tab, run_tab = st.tabs(["Model Performance", "Price Prediction"])
    with performance_tab: _performance()
    with run_tab: _prediction_runner()

