"""Local tests for inference-only registry selection and Dagster job topology."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from orchestration.assets.inference_assets import build_candidate_query, select_registered_model
from orchestration.definitions import defs


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

    def test_definitions_have_exactly_four_ml_jobs(self) -> None:
        """Full-pipeline orchestration is intentionally absent."""
        expected = {"price_retraining_job", "price_prediction_job", "segmentation_retraining_job", "segmentation_assignment_job"}
        self.assertEqual({job.name for job in defs.jobs}, expected)


if __name__ == "__main__":
    unittest.main()
