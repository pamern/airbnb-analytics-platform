"""Local-only high-level training and assignment entry points."""

from __future__ import annotations

import argparse
import logging
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.common.artifact_manager import create_versioned_artifact_dir, save_model_artifact, write_json
from ml.common.paths import SEGMENTATION_ARTIFACTS_DIR, SEGMENTATION_OUTPUTS_DIR
from ml.common.run_metadata import build_model_registry_record, build_training_run_record
from ml.listing_segmentation.config import REQUIRED_COLUMNS, SEGMENT_MAP, SegmentationConfig
from ml.listing_segmentation.data import load_local_segmentation_data, validate_segmentation_schema
from ml.listing_segmentation.evaluate import build_segmentation_metrics_long_format, evaluate_segmentation_model
from ml.listing_segmentation.prediction import assign_clusters, load_segmentation_model
from ml.listing_segmentation.profiles import build_cluster_assignments, build_cluster_profiles
from ml.listing_segmentation.training import build_segmentation_pipeline, train_segmentation_model

LOGGER = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Local results from a segmentation train run."""

    model: object
    model_version: str
    metrics: dict[str, object]
    artifact_paths: dict[str, Path]
    assignments: pd.DataFrame
    profiles: pd.DataFrame
    metric_records: pd.DataFrame
    run: dict[str, object]
    registry: dict[str, object]


def _new_model_version() -> str:
    return "segment_v" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _output_paths(root: Path, version: str) -> dict[str, Path]:
    return {"assignments": root / "csv" / f"{version}_cluster_assignments.csv", "metrics": root / "csv" / f"{version}_segmentation_metrics.csv", "profiles": root / "profiles" / f"{version}_cluster_profiles.csv", "run": root / "metadata" / f"{version}_training_run.json", "registry": root / "metadata" / f"{version}_model_registry.json"}


def _write_outputs(paths: dict[str, Path], assignments: pd.DataFrame, profiles: pd.DataFrame, metric_records: pd.DataFrame, run: dict[str, object], registry: dict[str, object]) -> None:
    for path in paths.values(): path.parent.mkdir(parents=True, exist_ok=True)
    assignments.to_csv(paths["assignments"], index=False); profiles.to_csv(paths["profiles"], index=False); metric_records.to_csv(paths["metrics"], index=False)
    write_json(paths["run"], run); write_json(paths["registry"], registry)


def run_segmentation_training_pipeline(data: pd.DataFrame, config: SegmentationConfig | None = None) -> TrainingResult:
    """Train KMeans locally from a caller-provided DataFrame."""
    config = config or SegmentationConfig()
    validate_segmentation_schema(data, REQUIRED_COLUMNS)
    model = train_segmentation_model(build_segmentation_pipeline(config), data.loc[:, list(config.model_features)])
    version = _new_model_version(); now = datetime.now(timezone.utc)
    assignments = build_cluster_assignments(model, data, model_version=version, assigned_at=now)
    metrics = evaluate_segmentation_model(model, data, assignments["cluster_id"].to_numpy())
    profiles = build_cluster_profiles(data, assignments, model_version=version, created_at=now)
    artifact_dir = create_versioned_artifact_dir(Path(config.artifact_root or SEGMENTATION_ARTIFACTS_DIR), version)
    model_path = save_model_artifact(model, artifact_dir)
    artifact_paths = {"model": model_path, "feature_schema": write_json(artifact_dir / "feature_schema.json", {"features": list(config.model_features), "feature_set_version": config.feature_set_version}), "training_config": write_json(artifact_dir / "training_config.json", asdict(config)), "metrics": write_json(artifact_dir / "metrics.json", metrics), "cluster_mapping": write_json(artifact_dir / "cluster_mapping.json", {str(key): value for key, value in SEGMENT_MAP.items()})}
    metric_records = build_segmentation_metrics_long_format(metrics, model_version=version)
    run = build_training_run_record(run_id="run_segment_" + now.strftime("%Y%m%d_%H%M%S"), model_version=version, training_mode="train", model_name=config.algorithm, status="success")
    registry = build_model_registry_record(model_version=version, model_name=config.algorithm, artifact_path=str(model_path))
    output_paths = _output_paths(Path(config.output_root or SEGMENTATION_OUTPUTS_DIR), version)
    _write_outputs(output_paths, assignments, profiles, metric_records, run, registry)
    LOGGER.info("Segmentation succeeded run=%s version=%s rows=%d clusters=%d silhouette=%s artifact=%s", run["run_id"], version, len(data), config.n_clusters, metrics.get("silhouette_score"), model_path)
    return TrainingResult(model, version, metrics, artifact_paths, assignments, profiles, metric_records, run, registry)


def run_segmentation_assignment_pipeline(data: pd.DataFrame, *, model_version: str, artifact_root: Path = SEGMENTATION_ARTIFACTS_DIR) -> pd.DataFrame:
    """Assign clusters using a persisted local artifact without refitting."""
    path = artifact_root / model_version / "model.joblib"
    return assign_clusters(load_segmentation_model(path), data, required_features=SegmentationConfig().model_features, model_version=model_version)


def _synthetic_data(rows: int = 24) -> pd.DataFrame:
    """Create a Gold-compatible fixture for the isolated smoke test."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({"listing_id": range(1, rows + 1), "price": rng.uniform(500, 3000, rows), "room_type": rng.choice(["Entire home/apt", "Private room"], rows), "property_base_group": rng.choice(["Apartment / Condo", "House / Home"], rows), "accommodates": rng.integers(1, 8, rows), "bedrooms": rng.uniform(1, 4, rows), "bathrooms": rng.uniform(1, 3, rows), "beds": rng.uniform(1, 5, rows), "amenities_count": rng.integers(5, 50, rows), "minimum_nights_log": rng.uniform(0, 3, rows)})


def main() -> None:
    """Run local training or artifact-based assignment from the command line."""
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path); parser.add_argument("--mode", choices=["train", "assign"], default="train"); parser.add_argument("--model-version"); parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO)
    if not args.smoke_test and args.input is None: parser.error("--input is required unless --smoke-test is used")
    if args.mode == "assign":
        if not args.model_version: parser.error("--model-version is required with --mode assign")
        data = load_local_segmentation_data(args.input); print(run_segmentation_assignment_pipeline(data, model_version=args.model_version).head())
    elif args.smoke_test:
        with tempfile.TemporaryDirectory() as directory:
            result = run_segmentation_training_pipeline(_synthetic_data(), SegmentationConfig(artifact_root=directory, output_root=directory)); print(f"Smoke test complete: {result.model_version}")
    else:
        result = run_segmentation_training_pipeline(load_local_segmentation_data(args.input)); print(f"Training complete: {result.model_version}")


if __name__ == "__main__": main()
