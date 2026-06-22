"""Reusable local price-prediction training and inference pipeline."""

from ml.price_modeling.config import PriceModelConfig

__all__ = ["PriceModelConfig", "run_price_training_pipeline"]


def __getattr__(name: str):
    """Lazily expose the pipeline entry point without import-time side effects."""
    if name == "run_price_training_pipeline":
        from ml.price_modeling.pipeline import run_price_training_pipeline
        return run_price_training_pipeline
    raise AttributeError(name)
