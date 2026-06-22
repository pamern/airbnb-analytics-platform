"""Versioned local artifact persistence with safe JSON serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np


def json_default(value: Any) -> Any:
    """Convert common NumPy and pathlib values to JSON-compatible values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def create_versioned_artifact_dir(root: Path, model_version: str) -> Path:
    """Create and return an unused artifact directory for ``model_version``."""
    if not model_version or Path(model_version).name != model_version:
        raise ValueError("model_version must be a non-empty directory name")
    path = root / model_version
    if path.exists():
        raise FileExistsError(f"Artifact version already exists: {path}")
    path.mkdir(parents=True)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write UTF-8 JSON, creating only the target parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")
    return path


def save_model_artifact(model: Any, artifact_dir: Path) -> Path:
    """Persist a model and verify the saved object can be loaded for prediction."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "model.joblib"
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite artifact: {path}")
    joblib.dump(model, path)
    loaded = joblib.load(path)
    if not hasattr(loaded, "predict"):
        raise RuntimeError(f"Saved artifact is not predictive: {path}")
    return path
