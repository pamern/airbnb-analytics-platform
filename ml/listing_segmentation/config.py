"""Configuration for the listing segmentation KMeans pipeline."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)

MODEL_NAME = "listing_segment_kmeans"
MODEL_DISPLAY_NAME = "KMeans"
SOURCE_TABLE = "gold.gold_cluster_model_features"
SEGMENT_TABLE = "gold.gold_listing_segments"

IDENTIFIER_COLUMNS = ["listing_id"]
CATEGORICAL_FEATURES = ["room_type", "property_base_group"]
NUMERICAL_FEATURES = [
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities_count",
    "minimum_nights_log",
]
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES

OPTIONAL_PROFILE_COLUMNS = [
    "price",
    "minimum_nights",
    "property_type",
]
REQUIRED_COLUMNS = IDENTIFIER_COLUMNS + ["price"] + MODEL_FEATURES

N_CLUSTERS = 3
RANDOM_STATE = 42
KMEANS_N_INIT = 10
KMEANS_PARAMS = {
    "n_clusters": N_CLUSTERS,
    "random_state": RANDOM_STATE,
    "n_init": KMEANS_N_INIT,
}

ASSIGNMENT_COLUMNS = [
    "listing_id",
    "cluster_id",
    "segment_name",
    "distance_to_centroid",
    "run_id",
    "model_name",
    "model_version",
    "assigned_at",
]

SEGMENT_MAP = {
    0: "Standard short-stay listings",
    1: "Long-stay standard apartments",
    2: "Large short-stay group homes",
}

OUTPUT_ROOT = PROJECT_ROOT / "ml" / "outputs" / "listing_segmentation"
CSV_OUTPUT_DIR = OUTPUT_ROOT / "csv"
METADATA_OUTPUT_DIR = OUTPUT_ROOT / "metadata"
CHART_OUTPUT_DIR = OUTPUT_ROOT / "charts"

ARTIFACT_DIR = PROJECT_ROOT / "ml" / "artifacts"
ARTIFACT_SUFFIX = "listing_segment_kmeans.joblib"
