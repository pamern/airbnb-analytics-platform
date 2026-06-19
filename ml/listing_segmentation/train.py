"""Train the listing segmentation KMeans pipeline."""

from __future__ import annotations

import sys
import os
from pathlib import Path

import joblib
import numpy as np

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.listing_segmentation.config import (  # noqa: E402
    MODEL_DISPLAY_NAME,
    MODEL_FEATURES,
    SEGMENT_MAP,
)
from ml.listing_segmentation.data_loader import get_connection, load_cluster_features  # noqa: E402
from ml.listing_segmentation.database_writer import (  # noqa: E402
    get_motherduck_write_connection,
    write_listing_segments_to_motherduck,
)
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
    run_id = run_timestamp.strftime("%Y%m%d%H%M%S")
    model_version = run_timestamp.strftime("%Y%m%d_%H%M%S")
    assigned_at = run_timestamp.replace(tzinfo=None)

    use_motherduck_write_connection = (
        os.getenv("AIRBNB_DB_TARGET", "local").lower() == "motherduck"
        and os.getenv("ALLOW_MOTHERDUCK_WRITE") == "1"
    )
    connection = (
        get_motherduck_write_connection()
        if use_motherduck_write_connection
        else get_connection(read_only=True)
    )
    try:
        features = load_cluster_features(connection)

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
        clustered["run_id"] = run_id
        clustered["model_name"] = MODEL_DISPLAY_NAME
        clustered["model_version"] = model_version
        clustered["assigned_at"] = assigned_at

        metrics = evaluate_clustering(model, features, cluster_labels)
        profiles = build_cluster_profiles(clustered)
        metrics_frame = build_cluster_metrics_frame(metrics)
        centroids = build_centroids_frame(model)
        cluster_distribution = (
            clustered.groupby(["cluster_id", "segment_name"], dropna=False)
            .size()
            .reset_index(name="listing_count")
            .sort_values("cluster_id")
            .to_dict(orient="records")
        )

        csv_paths = save_cluster_outputs(clustered, profiles, metrics_frame, centroids)
        assignment_frame = clustered[
            [
                "listing_id",
                "cluster_id",
                "segment_name",
                "distance_to_centroid",
                "run_id",
                "model_name",
                "model_version",
                "assigned_at",
            ]
        ].copy()
        database_write = write_listing_segments_to_motherduck(
            assignment_frame,
            expected_row_count=len(features),
            connection=connection if use_motherduck_write_connection else None,
        )
        metadata_paths = save_metadata(
            run_timestamp=run_timestamp,
            run_id=run_id,
            model_version=model_version,
            assigned_at=run_timestamp.isoformat(),
            row_count=len(features),
            metrics=metrics,
            artifact_path=artifact_path,
            cluster_distribution=cluster_distribution,
            database_write=database_write,
        )
        save_all_charts(model, clustered, profiles)
    finally:
        connection.close()

    return {
        "row_count": len(features),
        "artifact_path": artifact_path,
        "metrics": metrics,
        "csv_paths": csv_paths,
        "metadata_paths": metadata_paths,
        "database_write": database_write,
    }


def main() -> None:
    result = train_listing_segment_model()
    print("Listing segmentation training completed")
    print(f"Rows: {result['row_count']:,}")
    print(f"Artifact: {result['artifact_path']}")
    print(f"MotherDuck write: {result['database_write']}")
    print(f"Metrics: {result['metrics']}")


if __name__ == "__main__":
    main()
