"""Local tests for inference-only registry selection and Dagster job topology."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from dagster import AssetKey

from orchestration.assets.inference_assets import build_candidate_query, select_registered_model
from orchestration.definitions import defs
from orchestration.jobs.data_jobs import bronze_ingestion_selection, data_refresh_selection, dbt_analytics_selection


class OrchestrationInferenceTests(unittest.TestCase):
    """Verify inference selection never silently falls back from a champion."""

    def test_champion_is_preferred(self) -> None:
        """Champion is chosen even when a candidate is present."""
        with tempfile.TemporaryDirectory() as directory:
            champion = Path(directory) / "champion.joblib"; candidate = Path(directory) / "candidate.joblib"
            champion.touch(); candidate.touch()
            records = pd.DataFrame([
                {"model_version": "candidate", "artifact_path": candidate, "model_name": "price_model", "stage": "CANDIDATE", "is_active": False},
                {"model_version": "champion", "artifact_path": champion, "model_name": "price_model", "stage": "CHAMPION", "is_active": True},
            ])
            selected = select_registered_model(records, model_name="price_model")
            self.assertEqual(selected.model_version, "champion")

    def test_candidate_is_never_an_inference_fallback(self) -> None:
        """Candidate-only registry always fails; inference requires a Champion."""
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "candidate.joblib"; artifact.touch()
            records = pd.DataFrame([{"model_version": "candidate", "artifact_path": artifact, "model_name": "segmentation_model", "stage": "CANDIDATE", "is_active": False}])
            with self.assertRaises(RuntimeError):
                select_registered_model(records, model_name="segmentation_model")

    def test_multiple_active_champions_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.joblib"; second = Path(directory) / "second.joblib"
            first.touch(); second.touch()
            records = pd.DataFrame([
                {"model_version": "one", "artifact_path": first, "model_name": "price_model", "stage": "CHAMPION", "is_active": True},
                {"model_version": "two", "artifact_path": second, "model_name": "price_model", "stage": "CHAMPION", "is_active": True},
            ])
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                select_registered_model(records, model_name="price_model")

    def test_candidate_query_is_null_safe_and_bounded(self) -> None:
        query, parameters = build_candidate_query(feature_table="gold.features", result_table="gold.results", result_time_column="predicted_at", model_version="v1", result_type_filter="batch")
        self.assertIn("row_number() OVER", query)
        self.assertIn("IS DISTINCT FROM", query)
        self.assertIn("NOT EXISTS", query)
        self.assertIn("LIMIT ?", query)
        self.assertEqual(parameters, ["batch", "v1", "v1", "v1", 100])

    def test_definitions_expose_the_three_data_jobs_and_four_unchanged_ml_jobs(self) -> None:
        expected = {"bronze_ingestion_job", "dbt_analytics_build_job", "data_refresh_job", "price_retraining_job", "price_prediction_job", "segmentation_retraining_job", "segmentation_assignment_job"}
        self.assertEqual({job.name for job in defs.jobs}, expected)

    def test_bronze_ingestion_selection_excludes_dbt_and_ml_assets(self) -> None:
        keys = {"/".join(key.path) for key in bronze_ingestion_selection.resolve(defs.resolve_asset_graph())}
        self.assertIn("raw_source_validation", keys)
        self.assertIn("airbnb_bronze/bronze_listings", keys)
        self.assertFalse(any(key.startswith(("silver/", "gold/", "price_", "segmentation_", "current_", "write_")) for key in keys))

    def test_dbt_analytics_selection_contains_warehouse_models_only(self) -> None:
        keys = {"/".join(key.path) for key in dbt_analytics_selection.resolve(defs.resolve_asset_graph())}
        self.assertIn("silver/silver_listings", keys)
        self.assertIn("gold/gold_price_model_features", keys)
        self.assertIn("gold/gold_cluster_model_features", keys)
        self.assertFalse(any("training_result" in key or "batch_predictions" in key or "registry_records" in key for key in keys))

    def test_graph_links_bronze_to_silver_and_features_to_inference(self) -> None:
        graph = defs.resolve_asset_graph()
        silver_parents = {"/".join(key.path) for key in graph.get(AssetKey(["silver", "silver_listings"])).parent_keys}
        prediction_parents = {"/".join(key.path) for key in graph.get(AssetKey(["price_batch_predictions"])).parent_keys}
        self.assertIn("airbnb_bronze/bronze_listings", silver_parents)
        self.assertIn("gold/gold_price_model_features", prediction_parents)

    def test_data_refresh_selection_has_ingestion_analytics_and_inference_without_training(self) -> None:
        keys = {"/".join(key.path) for key in data_refresh_selection.resolve(defs.resolve_asset_graph())}
        required = {"raw_source_validation", "airbnb_bronze/bronze_listings", "silver/silver_listings", "gold/gold_price_model_features", "gold/gold_cluster_model_features", "current_price_champion", "price_batch_predictions", "write_price_batch_predictions", "current_segmentation_champion", "segmentation_assignments", "write_segmentation_assignments"}
        self.assertTrue(required.issubset(keys))
        self.assertFalse(any(key in keys for key in {"price_training_result", "segmentation_training_result", "price_registry_records", "segmentation_registry_records"}))


if __name__ == "__main__":
    unittest.main()
