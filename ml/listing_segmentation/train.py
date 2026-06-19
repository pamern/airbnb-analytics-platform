"""Train the listing segmentation KMeans pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.listing_segmentation.config import MODEL_FEATURES, SEGMENT_MAP  # noqa: E402
from ml.listing_segmentation.data_loader import get_connection, load_cluster_features  # noqa: E402
from ml.listing_segmentation.evaluate import (  # noqa: E402
    build_centroids_frame,
    build_cluster_metrics_frame,
    build_cluster_profiles,
    evaluate_clustering,
    transform_features,
)
from ml.listing_segmentation.preprocessing import build_listing_segment_pipeline  # noqa: E402
from ml.listing_segmentation.utils import (  # noqa: E402
    build_artifact_path,
    save_cluster_outputs,
    save_metadata,
    save_model_artifact,
    utc_timestamp,
)
from ml.listing_segmentation.visualization import save_all_charts  # noqa: E402


def train_listing_segment_model():
    run_timestamp = utc_timestamp()

    connection = get_connection(read_only=True)
    try:
        features = load_cluster_features(connection)
    finally:
        connection.close()

    model = build_listing_segment_pipeline()
    cluster_labels = model.fit_predict(features[MODEL_FEATURES])
    transformed = transform_features(model, features)
    distances = model.named_steps["kmeans"].transform(transformed)
    distance_to_centroid = distances[np.arange(len(features)), cluster_labels]

    artifact_path = build_artifact_path(run_timestamp)
    save_model_artifact(model, artifact_path)
    loaded_model = joblib.load(artifact_path)
    loaded_model.predict(features[MODEL_FEATURES].head(1))

    clustered = features.copy()
    clustered["cluster_id"] = cluster_labels.astype(int)
    clustered["distance_to_centroid"] = distance_to_centroid
    clustered["segment_name"] = clustered["cluster_id"].map(SEGMENT_MAP).fillna("Unknown")
    clustered["artifact_path"] = str(artifact_path)
    clustered["run_timestamp"] = run_timestamp.isoformat()

    metrics = evaluate_clustering(model, features, cluster_labels)
    profiles = build_cluster_profiles(clustered)
    metrics_frame = build_cluster_metrics_frame(metrics)
    centroids = build_centroids_frame(model)

    csv_paths = save_cluster_outputs(clustered, profiles, metrics_frame, centroids)
    metadata_paths = save_metadata(
        run_timestamp=run_timestamp,
        row_count=len(features),
        metrics=metrics,
        artifact_path=artifact_path,
    )
    save_all_charts(model, clustered, profiles)

    return {
        "row_count": len(features),
        "artifact_path": artifact_path,
        "metrics": metrics,
        "csv_paths": csv_paths,
        "metadata_paths": metadata_paths,
    }


def main() -> None:
    result = train_listing_segment_model()
    print("Listing segmentation training completed")
    print(f"Rows: {result['row_count']:,}")
    print(f"Artifact: {result['artifact_path']}")
    print(f"Metrics: {result['metrics']}")


if __name__ == "__main__":
    main()
