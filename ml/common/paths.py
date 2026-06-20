"""Repository-relative paths for ML modules."""

from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Return the repository root without depending on the working directory."""
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("Unable to locate repository root from ml.common.paths")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
ML_ROOT = REPO_ROOT / "ml"
ARTIFACTS_ROOT = ML_ROOT / "artifacts"
OUTPUTS_ROOT = ML_ROOT / "outputs"
PRICE_ARTIFACTS_DIR = ARTIFACTS_ROOT / "price_modeling"
PRICE_OUTPUTS_DIR = OUTPUTS_ROOT / "price_modeling"
SEGMENTATION_ARTIFACTS_DIR = ARTIFACTS_ROOT / "listing_segmentation"
SEGMENTATION_OUTPUTS_DIR = OUTPUTS_ROOT / "listing_segmentation"
