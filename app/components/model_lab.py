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
    get_shap_sample_artifact,
)
from services.price_prediction_service import (
    get_active_price_champion, get_comparable_listings, get_price_candidates,
    get_price_input_features, get_price_input_options, get_price_model_metrics,
    predict_single_listing, set_price_champion, PRICE_INPUT_SCHEMA,
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
    versions = ["All"] + (registry["model_version"].dropna().astype(str).drop_duplicates().tolist() if not registry.empty else [])
    selected_version = cols[2].selectbox("Model Version", versions, key=f"model_performance_version_{model_name}")
    runs, _ = get_model_runs(model_name, None, None)
    types = ["All"] + (runs["run_type"].dropna().astype(str).drop_duplicates().tolist() if not runs.empty else [])
    run_type = cols[3].selectbox("Run Type", types, key=f"model_performance_run_type_{model_name}")
    selected_dates = cols[4].date_input("Date Range", (date.today() - timedelta(days=90), date.today()), key="model_performance_dates")
    dates = tuple(selected_dates) if isinstance(selected_dates, tuple) else (selected_dates, selected_dates)
    return {"model_type": model_type, "model_name": model_name, "stage": stage, "version": None if selected_version == "All" else selected_version, "run_type": None if run_type == "All" else run_type, "date_from": dates[0], "date_to": dates[-1]}


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
    values = metrics.copy()
    if version: values = values[values["model_version"].astype(str).eq(version)]
    if test_only: values = values[values["dataset_split"].astype(str).str.upper().eq("TEST")]
    values = values[values["metric_name"].astype(str).str.lower().eq(key)]
    return None if values.empty else values.iloc[0]["metric_value"]


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
    trend, error = get_metric_trend("price_model", filters["date_from"], filters["date_to"])
    if _error(error) or trend.empty: return
    metric_names = sorted(trend["metric_name"].dropna().astype(str).unique().tolist())
    splits = sorted(trend["dataset_split"].fillna("UNSPECIFIED").astype(str).unique().tolist())
    controls = st.columns(2)
    selected_metrics = controls[0].multiselect("Metrics", metric_names, default=metric_names, key="price_metric_trend")
    selected_splits = controls[1].multiselect("Dataset Splits", splits, default=splits, key="price_metric_trend_splits")
    visible = trend[
        trend["metric_name"].astype(str).isin(selected_metrics)
        & trend["dataset_split"].fillna("UNSPECIFIED").astype(str).isin(selected_splits)
    ]
    if visible.empty: st.info("No successful runs match the selected metric and dataset split."); return
    visible = visible.assign(series=lambda frame: frame["metric_name"].astype(str) + " · " + frame["dataset_split"].fillna("UNSPECIFIED").astype(str))
    fig = px.line(visible, x="started_at", y="metric_value", color="series", symbol="model_version", markers=True, hover_data=["model_version", "dataset_split", "started_at"], color_discrete_sequence=[T["chart_primary"], T["chart_secondary"], T["chart_success"], T["chart_danger"]])
    st.plotly_chart(_layout(fig), use_container_width=True)


def _normalise_shap(frame: pd.DataFrame, allowed: list[str]) -> pd.DataFrame:
    columns = {str(column).lower(): column for column in frame.columns}
    feature = columns.get("feature_name") or columns.get("source_feature")
    shap = columns.get("shap_value")
    value = columns.get("feature_value")
    if not feature or not shap: return pd.DataFrame()
    result = frame.rename(columns={feature: "feature_name", shap: "shap_value"}).copy()
    result["feature_value"] = result[value] if value else None
    result = result[result["feature_name"].astype(str).isin(allowed)].dropna(subset=["shap_value"])
    return result


def _shap_views(version: str | None) -> None:
    importance, importance_error = get_feature_importance(version)
    _section("Global SHAP Feature Importance", "Mean absolute SHAP value on the evaluation sample. SHAP values explain predictions on the log-price scale.")
    if _error(importance_error): return
    if importance.empty: st.info("No SHAP feature importance is available for this model version."); return
    top = importance.head(15); st.plotly_chart(_layout(px.bar(top.sort_values("importance_value"), x="importance_value", y="feature_name", orientation="h", color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
    raw, artifact_error = get_shap_sample_artifact(version)
    _section("SHAP Impact Overview", "Positive SHAP values push the predicted log-price upward. Negative values push it downward.")
    if _error(artifact_error): return
    shap = _normalise_shap(raw, top["feature_name"].astype(str).tolist())
    if shap.empty: st.info("The SHAP sample artifact does not contain the fields needed for impact views."); return
    numeric_color = pd.to_numeric(shap["feature_value"], errors="coerce")
    fig = px.strip(shap, x="shap_value", y="feature_name", color=numeric_color if numeric_color.notna().any() else None, hover_data=["feature_value"], color_continuous_scale=[T["color_primary_soft"], T["chart_primary"]])
    fig.add_vline(x=0, line_color=T["chart_reference"], line_dash="dash"); st.plotly_chart(_layout(fig, 420), use_container_width=True)
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
    cols[0].metric("Active Champion", str(champion["model_version"]) if champion is not None else "No Champion")
    for col, (key, label) in zip(cols[1:4], PRICE_METRICS.items(), strict=True): col.metric(f"{label} — TEST", _number(_metric(metrics, key, version)))
    cols[4].metric("Model Version", version or "N/A")
    if champion is None: st.warning("No active Price Model Champion is available.")
    _error(metric_error)
    predictions, prediction_error = get_price_evaluation_predictions(version)
    if not _error(prediction_error):
        if predictions.empty: st.info("No evaluation predictions are available for this model version.")
        else: _price_scatter_and_residual(predictions, version); _error_by_band(predictions)
    _shap_views(version); _metric_trend(current); _tables("price_model", registry, current)


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
    cols[0].metric("Active Champion", str(champion["model_version"]) if champion is not None else "No Champion")
    for col, (key, label) in zip(cols[1:4], SEGMENTATION_METRICS.items(), strict=True): col.metric(label, _number(_metric(metrics, key, version, test_only=False)))
    cols[4].metric("Number of Clusters", _number(profiles["cluster_id"].nunique(), 0) if "cluster_id" in profiles else "N/A")
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
    assignments, assignment_error = get_cluster_assignments(version); trend, trend_error = get_metric_trend("segmentation_model", current["date_from"], current["date_to"]); left, right = st.columns(2)
    with left:
        _section("Cluster Distribution", "Listing counts by cluster for the selected model version.")
        if not _error(assignment_error) and not assignments.empty: st.plotly_chart(_layout(px.bar(assignments, x="cluster_id", y="listing_count", color_discrete_sequence=[T["chart_primary"]])), use_container_width=True)
        elif not assignment_error: st.info("No cluster assignments are available for this model version.")
    with right:
        _section("Segmentation Metric Trend", "Metrics from successful segmentation runs.")
        if not _error(trend_error) and not trend.empty:
            metric_names = sorted(trend["metric_name"].dropna().astype(str).unique().tolist())
            selected_metrics = st.multiselect("Segmentation Metrics", metric_names, default=metric_names, key="segmentation_metric_trend")
            visible = trend[trend["metric_name"].astype(str).isin(selected_metrics)]
            if visible.empty: st.info("No successful runs match the selected metrics.")
            else: st.plotly_chart(_layout(px.line(visible, x="started_at", y="metric_value", color="metric_name", symbol="model_version", markers=True, hover_data=["model_version", "dataset_split", "started_at"], color_discrete_sequence=[T["chart_primary"], T["chart_secondary"], T["chart_success"]])), use_container_width=True)
    _section("Cluster Profiles", "Available profile fields are read directly from the Gold table.")
    if not _error(profile_error): st.dataframe(profiles, use_container_width=True, hide_index=True) if not profiles.empty else st.info("No cluster profiles are available for this model version.")
    _tables("segmentation_model", registry, current)


def _performance() -> None:
    _styles(); filters = _filter_bar()
    if filters["model_type"] == "Price Model": _price_model(filters)
    else: _segmentation_model(filters)


def _prediction_inputs(features: list[str]) -> tuple[dict[str, object], bool, bool]:
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
                            values[name] = st.selectbox(label, choices, key=f"price_input_{name}")
                        else:
                            st.caption(f"{label}: no Gold-table values available")
                    elif spec["kind"] == "integer":
                        values[name] = st.number_input(label, min_value=int(spec["min"]), max_value=int(spec["max"]), value=int(spec["default"]), step=1, key=f"price_input_{name}")
                    else:
                        values[name] = st.number_input(label, min_value=float(spec["min"]), max_value=float(spec["max"]), value=float(spec["default"]), step=float(spec["step"]), key=f"price_input_{name}")
                if group == "host":
                    predict_pressed = st.form_submit_button("Predict Price", type="primary", use_container_width=True)
        reset_pressed = st.form_submit_button("Reset Inputs")
    return values, reset_pressed, predict_pressed


def _champion_card(champion: pd.Series | None) -> None:
    _section("Model Champion", "The active Price Model is the only model eligible for prediction.")
    if champion is None: st.error("No single active Price Model Champion is available. Prediction is disabled."); return
    metrics, error = get_price_model_metrics(str(champion["model_version"]))
    if _error(error): return
    cols = st.columns(3); cols[0].metric("Model Version", str(champion["model_version"])); cols[1].metric("Stage", str(champion["stage"])); cols[2].metric("Created At", str(champion.get("created_at", "N/A")))
    metric_cols = st.columns(3)
    for col, (key, label) in zip(metric_cols, PRICE_METRICS.items(), strict=True): col.metric(label, _number(_metric(metrics, key, str(champion["model_version"]))))


def _market_views(predicted_price: float, inputs: dict[str, object]) -> None:
    comparable, error = get_comparable_listings(inputs)
    _section("Comparable Listings", "Comparable listings use the same neighbourhood and room type with similar capacity.")
    if _error(error) or comparable.empty:
        if not error: st.info("No comparable listings are available for the selected input.")
        return
    st.dataframe(comparable, use_container_width=True, hide_index=True)
    reference = comparable["actual_price"].dropna()
    if len(reference) < 5: st.info("Insufficient market data for a reliable market position."); return
    percentile = float((reference <= predicted_price).mean()); position = "Above Median" if predicted_price > reference.median() else "At or Below Median"
    cols = st.columns(2); cols[0].metric("Price Percentile", f"{percentile:.0%}"); cols[1].metric("Market Position", position)
    _section("Price Position vs Market", "Reference group: same neighbourhood and room type with similar capacity.")
    fig = go.Figure(go.Box(x=reference, orientation="h", name="Comparable listings", marker_color=T["chart_primary"]))
    fig.add_vline(x=predicted_price, line_color=T["chart_danger"], line_width=3, annotation_text="Predicted price")
    st.plotly_chart(_layout(fig, 220), use_container_width=True)


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


def _prediction_runner() -> None:
    champion, champion_error = get_active_price_champion()
    features, schema_error = get_price_input_features(champion)
    _champion_card(champion)
    if champion_error: st.error(champion_error)
    if schema_error: st.error(schema_error); return
    inputs, reset, predict = _prediction_inputs(features)
    if reset: st.session_state.pop("price_prediction_result", None); st.rerun()
    if predict and champion is not None:
        missing = [name for name in features if name not in inputs]
        if missing: st.error("Complete the required fields before requesting a prediction.")
        else:
            price, error = predict_single_listing(inputs, champion)
            if error: st.error(error)
            else: st.session_state["price_prediction_result"] = {"price": price, "version": str(champion["model_version"]), "inputs": inputs, "time": pd.Timestamp.now()}
    result = st.session_state.get("price_prediction_result")
    if result:
            _section("Prediction Result", "Estimated nightly price from the active Champion artifact.")
            result_cols = st.columns(3)
            result_cols[0].metric("Predicted Nightly Price", _number(result["price"], 2))
            result_cols[1].metric("Suggested Range", "Not available")
            result_cols[2].metric("Confidence", "Not available")
            st.caption("No persisted prediction interval or confidence rule is configured for this Champion.")
            _section("Top Drivers", "Local SHAP explanation is unavailable unless the Champion artifact includes a compatible explainer.")
            st.info("SHAP explanation unavailable for this prediction.")
            _market_views(float(result["price"]), result["inputs"])
            _section("Prediction Notes", "Rule-based notes only use available model and market data.")
            st.info("Prediction notes will appear when local SHAP or sufficient comparable-market data is available.")
            history = st.session_state.setdefault("recent_price_predictions", []); history.insert(0, {"Time": result["time"], "Model Version": result["version"], "Predicted Price": result["price"], "Neighbourhood": result["inputs"].get("neighbourhood"), "Room Type": result["inputs"].get("room_type")})
            _section("Recent Predictions", "Session-only history; no predictions are written to the warehouse.")
            st.dataframe(pd.DataFrame(history[:10]), use_container_width=True, hide_index=True)
    _promotion_controls()


def render_model_lab_page() -> None:
    performance_tab, run_tab, cluster_tab, future_tab = st.tabs(["Model Performance", "Price Prediction", "Cluster", "Model 3"])
    with performance_tab: _performance()
    with run_tab: _prediction_runner()
    with cluster_tab: st.info("Cluster exploration workspace. Use Model Performance to review registered segmentation results.")
    with future_tab: st.info("Workspace reserved for a future model.")
