"""SHAP explainability for the fitted XGBoost price pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

SHAP_SAMPLE_SIZE = 1000
SHAP_RANDOM_STATE = 42
_TOLERANCE = 1e-5


@dataclass(frozen=True)
class ShapResult:
    """Validated global and sample-level SHAP results for one test-set sample."""

    transformed_importance: pd.DataFrame
    original_importance: pd.DataFrame
    sample_values: pd.DataFrame
    summary: dict[str, Any]


def _fitted_parts(fitted_pipeline: Pipeline) -> tuple[ColumnTransformer, Any]:
    try:
        return fitted_pipeline.named_steps["preprocessor"], fitted_pipeline.named_steps["model"]
    except KeyError as error:
        raise ValueError("Expected fitted pipeline steps named 'preprocessor' and 'model'") from error


def transformed_feature_mapping(preprocessor: ColumnTransformer) -> pd.DataFrame:
    """Map every fitted transformed column to one exact raw source feature."""
    names = list(preprocessor.get_feature_names_out())
    mapping: dict[str, tuple[str, str | None]] = {}
    for transformer_name, transformer, columns in preprocessor.transformers_:
        if transformer == "drop":
            continue
        source_columns = [str(column) for column in columns]
        fitted = preprocessor.named_transformers_[transformer_name]
        if transformer == "passthrough":
            local_names = source_columns
            source_for_local = source_columns
            categories: list[str | None] = [None] * len(local_names)
        else:
            final_transformer = fitted.steps[-1][1] if isinstance(fitted, Pipeline) else fitted
            if hasattr(final_transformer, "categories_"):
                local_names = []
                source_for_local = []
                categories = []
                encoded_names = list(final_transformer.get_feature_names_out(source_columns))
                for source, values in zip(source_columns, final_transformer.categories_):
                    expected_prefix = f"{source}_"
                    for encoded_name in (name for name in encoded_names if name.startswith(expected_prefix)):
                        local_names.append(encoded_name)
                        source_for_local.append(source)
                        if encoded_name == f"{source}_infrequent_sklearn":
                            categories.append("<infrequent>")
                        else:
                            matches = [str(value) for value in values if encoded_name == f"{source}_{value}"]
                            if len(matches) != 1:
                                raise ValueError(f"Unable to map OneHot output {encoded_name} to a category for {source}")
                            categories.append(matches[0])
            elif hasattr(fitted, "get_feature_names_out"):
                local_names = list(fitted.get_feature_names_out(source_columns))
                source_for_local = source_columns
                categories = [None] * len(local_names)
            else:
                local_names = source_columns
                source_for_local = source_columns
                categories = [None] * len(local_names)
        if not (len(local_names) == len(source_for_local) == len(categories)):
            raise ValueError(f"Unable to map transformed features for transformer {transformer_name}")
        for local_name, source, category in zip(local_names, source_for_local, categories):
            full_name = f"{transformer_name}__{local_name}"
            if full_name in mapping:
                raise ValueError(f"Duplicate transformed feature mapping: {full_name}")
            mapping[full_name] = (source, category)
    missing = [name for name in names if name not in mapping]
    if missing:
        raise ValueError(f"Unable to map transformed features: {missing}")
    return pd.DataFrame([{"feature_name": name, "source_feature": mapping[name][0], "category": mapping[name][1]} for name in names])


def _normalise_shap_output(explainer: shap.TreeExplainer, transformed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Support SHAP's Explanation and ndarray APIs while enforcing a 2D result."""
    output = explainer(transformed)
    values = np.asarray(getattr(output, "values", output))
    base = np.asarray(getattr(output, "base_values", explainer.expected_value))
    values = np.squeeze(values)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2:
        raise ValueError(f"Unexpected SHAP value shape: {values.shape}")
    base = np.squeeze(base)
    if base.ndim == 0:
        base = np.full(values.shape[0], float(base))
    elif base.ndim == 1 and len(base) == values.shape[0]:
        base = base.astype(float)
    else:
        raise ValueError(f"Unexpected SHAP base-value shape: {base.shape}")
    return values.astype(float), base


def _direction(values: np.ndarray) -> np.ndarray:
    return np.where(values > 0, "INCREASE", np.where(values < 0, "DECREASE", "NEUTRAL"))


def _display_value(raw: object, transformed_value: float, category: str | None) -> str | None:
    if category is not None:
        return category if transformed_value == 1 else None
    if pd.isna(raw):
        return "<missing>"
    return str(raw)


def calculate_shap_results(fitted_pipeline: Pipeline, X_test: pd.DataFrame, test_metadata: pd.DataFrame, *, run_id: str, model_name: str, model_version: str, sample_size: int = SHAP_SAMPLE_SIZE, random_state: int = SHAP_RANDOM_STATE) -> ShapResult:
    """Create reproducible global SHAP importance and transformed long-format detail."""
    if X_test.empty:
        raise ValueError("Cannot calculate SHAP from an empty test set")
    if not X_test.index.is_unique or not test_metadata.index.is_unique:
        raise ValueError("X_test and test metadata require unique indexes for SHAP linkage")
    sample = X_test.sample(n=min(sample_size, len(X_test)), random_state=random_state)
    metadata = test_metadata.reindex(sample.index)
    if metadata["listing_id"].isna().any():
        raise ValueError("SHAP sample could not be linked to listing_id")
    preprocessor, estimator = _fitted_parts(fitted_pipeline)
    transformed_raw = preprocessor.transform(sample)
    transformed = transformed_raw.toarray() if sparse.issparse(transformed_raw) else np.asarray(transformed_raw)
    feature_names = list(preprocessor.get_feature_names_out())
    if len(feature_names) != transformed.shape[1]:
        raise ValueError(f"SHAP feature-name mismatch run_id={run_id} model_version={model_version} feature_name_count={len(feature_names)} transformed_column_count={transformed.shape[1]}")
    mapping = transformed_feature_mapping(preprocessor)
    explainer = shap.TreeExplainer(estimator)
    shap_values, base_values = _normalise_shap_output(explainer, transformed)
    if shap_values.shape != transformed.shape:
        raise ValueError(f"SHAP matrix shape {shap_values.shape} does not match transformed input {transformed.shape}")
    predictions = np.asarray(estimator.predict(transformed), dtype=float)
    if not np.allclose(base_values + shap_values.sum(axis=1), predictions, rtol=_TOLERANCE, atol=_TOLERANCE):
        raise ValueError("SHAP additivity check failed for log_price predictions")
    if not np.isfinite(shap_values).all() or not np.isfinite(predictions).all():
        raise ValueError("SHAP values or predictions contain non-finite values")
    importance = mapping.copy()
    importance["importance_value"] = np.abs(shap_values).mean(axis=0)
    importance["feature_level"] = "TRANSFORMED"
    importance = importance.sort_values("importance_value", ascending=False, kind="stable").reset_index(drop=True)
    importance["importance_rank"] = np.arange(1, len(importance) + 1)
    transformed_importance = importance.loc[:, ["feature_name", "source_feature", "feature_level", "importance_value", "importance_rank"]]
    original_importance = transformed_importance.groupby("source_feature", as_index=False)["importance_value"].sum()
    original_importance["feature_name"] = original_importance["source_feature"]
    original_importance["feature_level"] = "ORIGINAL"
    original_importance = original_importance.sort_values("importance_value", ascending=False, kind="stable").reset_index(drop=True)
    original_importance["importance_rank"] = np.arange(1, len(original_importance) + 1)
    original_importance = original_importance.loc[:, ["feature_name", "source_feature", "feature_level", "importance_value", "importance_rank"]]
    raw_values = sample.reindex(columns=mapping["source_feature"].unique())
    detail_rows: list[dict[str, object]] = []
    for row_index, (sample_index, raw_row) in enumerate(sample.iterrows()):
        for feature_index, feature in mapping.iterrows():
            source = str(feature["source_feature"]); transformed_value = float(transformed[row_index, feature_index]); shap_value = float(shap_values[row_index, feature_index])
            detail_rows.append({"sample_id": f"test_{sample_index}", "listing_id": int(metadata.loc[sample_index, "listing_id"]), "run_id": run_id, "model_name": model_name, "model_version": model_version, "feature_name": feature["feature_name"], "source_feature": source, "feature_level": "TRANSFORMED", "feature_value": transformed_value, "feature_value_display": _display_value(raw_row[source], transformed_value, feature["category"]), "shap_value": shap_value, "abs_shap_value": abs(shap_value), "direction": _direction(np.asarray([shap_value]))[0], "base_value": float(base_values[row_index]), "prediction_log_price": float(predictions[row_index]), "predicted_price": float(np.expm1(predictions[row_index])), "dataset_split": "TEST"})
    detail = pd.DataFrame(detail_rows)
    if len(detail) != len(sample) * len(feature_names) or detail.duplicated(["sample_id", "feature_name", "feature_level"]).any():
        raise ValueError("Invalid or duplicate SHAP detail records")
    summary: dict[str, Any] = {"run_id": run_id, "model_name": model_name, "model_version": model_version, "sample_size": len(sample), "transformed_feature_count": len(feature_names), "original_feature_count": len(original_importance), "dataset_split": "TEST", "random_state": random_state, "explainer_type": "TreeExplainer", "importance_method": "shap", "explanation_output_space": "log_price"}
    return ShapResult(transformed_importance, original_importance, detail, summary)


def explain_single_prediction(fitted_pipeline: Pipeline, raw_input: dict[str, object] | pd.DataFrame) -> pd.DataFrame:
    """Return sorted, local SHAP contributions for one raw feature row on log_price scale."""
    frame = pd.DataFrame([raw_input]) if isinstance(raw_input, dict) else raw_input.copy()
    if len(frame) != 1:
        raise ValueError("Local SHAP explanation accepts exactly one prediction row")
    preprocessor, estimator = _fitted_parts(fitted_pipeline)
    required = list(preprocessor.feature_names_in_)
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Local SHAP input is missing features: {missing}")
    transformed_raw = preprocessor.transform(frame.loc[:, required])
    transformed = transformed_raw.toarray() if sparse.issparse(transformed_raw) else np.asarray(transformed_raw)
    mapping = transformed_feature_mapping(preprocessor)
    values, base = _normalise_shap_output(shap.TreeExplainer(estimator), transformed)
    prediction = float(estimator.predict(transformed)[0])
    if not np.isclose(float(base[0] + values[0].sum()), prediction, rtol=_TOLERANCE, atol=_TOLERANCE):
        raise ValueError("Local SHAP additivity check failed")
    rows = []
    for index, feature in mapping.iterrows():
        transformed_value = float(transformed[0, index]); source = str(feature["source_feature"]); value = float(values[0, index])
        rows.append({"base_value": float(base[0]), "prediction_log_price": prediction, "predicted_price": float(np.expm1(prediction)), "feature_name": feature["feature_name"], "source_feature": source, "feature_value": transformed_value, "feature_value_display": _display_value(frame.iloc[0][source], transformed_value, feature["category"]), "shap_value": value, "abs_shap_value": abs(value), "direction": _direction(np.asarray([value]))[0], "explanation_output_space": "log_price"})
    result = pd.DataFrame(rows).sort_values("abs_shap_value", ascending=False, kind="stable").reset_index(drop=True)
    result["importance_rank"] = np.arange(1, len(result) + 1)
    return result
