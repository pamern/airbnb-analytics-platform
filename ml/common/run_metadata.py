"""Local record builders that mirror future warehouse ML metadata tables."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TrainingRun:
    run_id: str
    model_version: str
    training_mode: str
    model_name: str
    started_at: str
    status: str


def build_training_run_record(**kwargs: Any) -> dict[str, Any]:
    """Build a future ``gold_ml_training_runs``-compatible record."""
    return asdict(TrainingRun(started_at=datetime.now(timezone.utc).isoformat(), **kwargs))


def build_model_registry_record(*, model_version: str, model_name: str, artifact_path: str) -> dict[str, Any]:
    """Build a local equivalent of a model registry record."""
    return {"model_version": model_version, "model_name": model_name, "artifact_path": artifact_path}


def build_model_metric_records(metrics: dict[str, float], *, model_version: str, dataset_type: str) -> pd.DataFrame:
    """Return long-format metric records without writing to a database."""
    evaluated_at = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame([
        {"model_version": model_version, "dataset_type": dataset_type, "metric_name": name,
         "metric_value": value, "metric_std": None, "evaluated_at": evaluated_at}
        for name, value in metrics.items()
    ])
