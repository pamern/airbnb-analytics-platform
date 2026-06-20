"""Synthetic tests for the local-only listing segmentation pipeline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ml.listing_segmentation.config import SegmentationConfig
from ml.listing_segmentation.pipeline import _synthetic_data, run_segmentation_assignment_pipeline, run_segmentation_training_pipeline


class ListingSegmentationTests(unittest.TestCase):
    """Verify the accepted KMeans setup can train and reload locally."""

    def test_train_save_load_and_assign(self) -> None:
        """Ensure model assignment remains stable after artifact persistence."""
        with tempfile.TemporaryDirectory() as directory:
            config = SegmentationConfig(artifact_root=directory, output_root=directory)
            data = _synthetic_data()
            result = run_segmentation_training_pipeline(data, config)
            assigned = run_segmentation_assignment_pipeline(data, model_version=result.model_version, artifact_root=Path(directory))
            self.assertEqual(len(assigned), len(data))
            self.assertEqual(set(assigned["cluster_name"]), set(result.assignments["cluster_name"]))
            self.assertEqual(set(assigned["cluster_id"]), set(result.assignments["cluster_id"]))
            self.assertEqual(list(result.metric_records.columns), ["model_version", "dataset_type", "metric_name", "metric_value", "metric_std", "evaluated_at"])
            self.assertTrue(result.artifact_paths["model"].is_file())


if __name__ == "__main__":
    unittest.main()
