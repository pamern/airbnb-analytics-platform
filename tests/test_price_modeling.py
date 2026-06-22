"""Synthetic checks for the local-only price modeling package."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ml.price_modeling.config import PriceModelConfig
from ml.price_modeling.pipeline import _synthetic_data, run_price_prediction_pipeline, run_price_training_pipeline
from ml.price_modeling.prediction import load_price_model
from ml.price_modeling.preprocessing import prepare_modeling_frame


class PriceModelingTests(unittest.TestCase):
    """Verify import-safe local training and artifact inference."""

    def test_retrain_save_load_and_predict(self) -> None:
        """Train on synthetic data and preserve prediction results after loading."""
        with tempfile.TemporaryDirectory() as directory:
            config = PriceModelConfig(artifact_root=directory, output_root=directory, run_error_analysis=False, run_explainability=False, xgb_n_estimators=10, n_jobs=1)
            result = run_price_training_pipeline(_synthetic_data(), config)
            loaded = load_price_model(result.artifact_paths["model"])
            record = prepare_modeling_frame(_synthetic_data(1)).drop(columns=["price", "property_type", "log_price"])
            expected = run_price_prediction_pipeline(result.model, record, config)
            actual = run_price_prediction_pipeline(loaded, record, config)
            self.assertEqual(list(result.metric_records.columns), ["model_version", "dataset_type", "metric_name", "metric_value", "metric_std", "evaluated_at"])
            self.assertAlmostEqual(float(expected.iloc[0]["predicted_price"]), float(actual.iloc[0]["predicted_price"]))
            self.assertTrue(Path(result.artifact_paths["model"]).is_file())
            self.assertTrue(Path(result.artifact_paths["shap_sample_values"]).is_file())
            self.assertEqual(set(result.shap_importance["feature_level"]), {"TRANSFORMED", "ORIGINAL"})
            self.assertTrue((result.shap_importance["importance_value"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
