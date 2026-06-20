"""Construction and fitting of the unchanged KMeans segmentation pipeline."""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.pipeline import Pipeline

from ml.listing_segmentation.config import SegmentationConfig
from ml.listing_segmentation.preprocessing import build_listing_segment_pipeline


def build_segmentation_estimator(config: SegmentationConfig) -> KMeans:
    """Build KMeans with exactly the accepted hyperparameters."""
    return KMeans(n_clusters=config.n_clusters, random_state=config.random_state, n_init=config.n_init)


def build_segmentation_pipeline(config: SegmentationConfig) -> Pipeline:
    """Build the existing preprocessor-plus-KMeans pipeline without fitting it."""
    pipeline = build_listing_segment_pipeline()
    pipeline.named_steps["kmeans"].set_params(**build_segmentation_estimator(config).get_params())
    return pipeline


def train_segmentation_model(model: Pipeline, features: pd.DataFrame) -> Pipeline:
    """Fit a complete segmentation pipeline only on caller-supplied features."""
    model.fit(features)
    return model
