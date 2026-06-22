"""Reusable local listing-segmentation pipeline."""

from ml.listing_segmentation.config import SegmentationConfig

__all__ = ["SegmentationConfig", "run_segmentation_training_pipeline"]


def __getattr__(name: str):
    """Lazily expose entry points without triggering pipeline imports."""
    if name == "run_segmentation_training_pipeline":
        from ml.listing_segmentation.pipeline import run_segmentation_training_pipeline
        return run_segmentation_training_pipeline
    raise AttributeError(name)

