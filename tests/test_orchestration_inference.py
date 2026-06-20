"""Local tests for inference-only registry selection and Dagster job topology."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from orchestration.assets.inference_assets import select_registered_model
from orchestration.definitions import defs


class OrchestrationInferenceTests(unittest.TestCase):
    """Verify inference selection never silently falls back from a champion."""

    def test_champion_is_preferred(self) -> None:
        """Champion is chosen even when a candidate is present."""
        with tempfile.TemporaryDirectory() as directory:
            champion = Path(directory) / "champion.joblib"; candidate = Path(directory) / "candidate.joblib"
            champion.touch(); candidate.touch()
            records = pd.DataFrame([
                {"model_version": "candidate", "artifact_path": candidate, "model_name": "XGBRegressor", "status": "CANDIDATE"},
                {"model_version": "champion", "artifact_path": champion, "model_name": "XGBRegressor", "status": "CHAMPION"},
            ])
            selected = select_registered_model(records, model_task="price_prediction", allow_latest_candidate_fallback=True)
            self.assertEqual(selected.model_version, "champion")

    def test_candidate_requires_explicit_fallback(self) -> None:
        """Candidate-only registry fails by default and succeeds when enabled."""
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "candidate.joblib"; artifact.touch()
            records = pd.DataFrame([{"model_version": "candidate", "artifact_path": artifact, "model_name": "KMeans", "status": "CANDIDATE"}])
            with self.assertRaises(RuntimeError):
                select_registered_model(records, model_task="listing_segmentation", allow_latest_candidate_fallback=False)
            self.assertEqual(select_registered_model(records, model_task="listing_segmentation", allow_latest_candidate_fallback=True).model_version, "candidate")

    def test_definitions_have_exactly_four_ml_jobs(self) -> None:
        """Full-pipeline orchestration is intentionally absent."""
        expected = {"price_retraining_job", "price_prediction_job", "segmentation_retraining_job", "segmentation_assignment_job"}
        self.assertEqual({job.name for job in defs.jobs}, expected)


if __name__ == "__main__":
    unittest.main()
