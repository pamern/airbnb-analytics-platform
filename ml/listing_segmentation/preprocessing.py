"""Preprocessing and sklearn pipeline construction."""

from __future__ import annotations

from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.listing_segmentation.config import (
    CATEGORICAL_FEATURES,
    KMEANS_PARAMS,
    NUMERICAL_FEATURES,
)


def build_listing_segment_pipeline() -> Pipeline:
    """Build a single sklearn Pipeline containing preprocessing and KMeans."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
            ("numeric", StandardScaler(), NUMERICAL_FEATURES),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("kmeans", KMeans(**KMEANS_PARAMS)),
        ]
    )
