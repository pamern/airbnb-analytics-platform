"""Warehouse persistence helpers for model lifecycle metadata and business outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from orchestration.resources.motherduck import MotherDuckResource

PRICE_PREDICTIONS_TABLE = "gold.gold_listing_price_predictions"
SEGMENT_ASSIGNMENTS_TABLE = "gold.gold_listing_cluster_assignments"
SEGMENT_PROFILES_TABLE = "gold.gold_cluster_profiles"
PRICE_MODEL_NAME = "price_model"
SEGMENTATION_MODEL_NAME = "segmentation_model"


def ensure_mlops_tables(connection: Any) -> None:
    """Create only the new MLOps metadata tables and Gold business-output tables."""
    connection.execute("CREATE SCHEMA IF NOT EXISTS mlops")
    connection.execute("CREATE SCHEMA IF NOT EXISTS gold")
    statements = [
        "CREATE TABLE IF NOT EXISTS mlops.model_runs (run_id VARCHAR, job_name VARCHAR, model_name VARCHAR, model_version VARCHAR, run_type VARCHAR, status VARCHAR, feature_snapshot VARCHAR, started_at TIMESTAMP, completed_at TIMESTAMP, artifact_path VARCHAR, error_message VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS mlops.model_metrics (run_id VARCHAR, model_name VARCHAR, model_version VARCHAR, metric_name VARCHAR, metric_value DOUBLE, dataset_split VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS mlops.model_registry (model_name VARCHAR, model_version VARCHAR, run_id VARCHAR, stage VARCHAR, is_active BOOLEAN, artifact_path VARCHAR, preprocessor_path VARCHAR, created_at TIMESTAMP, promoted_at TIMESTAMP, promoted_by VARCHAR)",
        "CREATE TABLE IF NOT EXISTS mlops.model_feature_importance (run_id VARCHAR NOT NULL, model_name VARCHAR NOT NULL, model_version VARCHAR NOT NULL, feature_name VARCHAR NOT NULL, source_feature VARCHAR NOT NULL, feature_level VARCHAR NOT NULL, importance_value DOUBLE NOT NULL, importance_rank INTEGER NOT NULL, importance_method VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL)",
        "CREATE TABLE IF NOT EXISTS gold.gold_listing_price_predictions (listing_id BIGINT, run_id VARCHAR, model_version VARCHAR, feature_hash VARCHAR, actual_price DOUBLE, predicted_price DOUBLE, actual_log_price DOUBLE, predicted_log_price DOUBLE, residual DOUBLE, absolute_error DOUBLE, prediction_type VARCHAR, predicted_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS gold.gold_listing_cluster_assignments (listing_id BIGINT, run_id VARCHAR, model_version VARCHAR, feature_hash VARCHAR, cluster_id INTEGER, cluster_name VARCHAR, distance_to_centroid DOUBLE, assigned_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS gold.gold_cluster_profiles (model_version VARCHAR, cluster_id INTEGER, cluster_name VARCHAR, listing_count BIGINT, median_price DOUBLE, avg_price DOUBLE, listing_share DOUBLE, accommodates_mean DOUBLE, bedrooms_mean DOUBLE, bathrooms_mean DOUBLE, beds_mean DOUBLE, amenities_count_mean DOUBLE, minimum_nights_log_mean DOUBLE, dominant_room_type VARCHAR, dominant_property_base_group VARCHAR, created_at TIMESTAMP)",
    ]
    for statement in statements:
        connection.execute(statement)
    connection.execute("ALTER TABLE mlops.model_feature_importance ADD COLUMN IF NOT EXISTS source_feature VARCHAR")
    connection.execute("ALTER TABLE mlops.model_feature_importance ADD COLUMN IF NOT EXISTS feature_level VARCHAR")


def start_run(motherduck: MotherDuckResource, *, run_id: str, job_name: str, model_name: str, model_version: str | None, run_type: str, artifact_path: str | None = None) -> None:
    """Record a Dagster run before work begins; idempotent for asset retries."""
    now = datetime.now(timezone.utc)
    with motherduck.transaction() as connection:
        ensure_mlops_tables(connection)
        exists = connection.execute("SELECT COUNT(*) FROM mlops.model_runs WHERE run_id = ?", [run_id]).fetchone()[0]
        if not exists:
            motherduck.append_dataframe("mlops.model_runs", pd.DataFrame([{"run_id": run_id, "job_name": job_name, "model_name": model_name, "model_version": model_version, "run_type": run_type, "status": "RUNNING", "feature_snapshot": None, "started_at": now, "completed_at": None, "artifact_path": artifact_path, "error_message": None, "created_at": now}]), connection=connection)


def finish_run(motherduck: MotherDuckResource, *, run_id: str, status: str, error_message: str | None = None) -> None:
    """Finish a previously recorded run, preserving a concise failure reason when present."""
    with motherduck.transaction() as connection:
        ensure_mlops_tables(connection)
        connection.execute("UPDATE mlops.model_runs SET status = ?, completed_at = ?, error_message = ? WHERE run_id = ?", [status, datetime.now(timezone.utc), error_message, run_id])
