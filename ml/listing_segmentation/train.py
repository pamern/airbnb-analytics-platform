"""Backward-compatible local-only runner for listing segmentation."""

from __future__ import annotations

from ml.listing_segmentation.pipeline import main, run_segmentation_training_pipeline


def train_listing_segment_model(data, config=None):
    """Train from caller-supplied local data; retained for import compatibility."""
    return run_segmentation_training_pipeline(data, config)


if __name__ == "__main__":
    main()
