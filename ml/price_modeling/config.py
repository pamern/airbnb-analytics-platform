"""Immutable configuration retained from the price-modeling research notebook."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ml.common.paths import PRICE_ARTIFACTS_DIR, PRICE_OUTPUTS_DIR


TrainingMode = Literal["retrain", "tune", "research"]

SELECTED_FEATURES = (
    "neighbourhood", "bedrooms", "room_type", "property_base_group", "host_response_time",
    "bathrooms", "accommodates", "review_scores_location", "host_response_rate",
    "host_listings_count", "calculated_host_listings_count", "host_total_listings_count",
    "host_acceptance_rate", "number_of_reviews_ltm", "minimum_nights",
)

BEST_XGB_PARAMETERS = {
    "learning_rate": 0.034246398779081366, "max_depth": 8, "min_child_weight": 4,
    "subsample": 0.7650915513722765, "colsample_bytree": 0.8207240159340592,
    "gamma": 0.03262752834716495, "reg_alpha": 0.001997728480368332,
    "reg_lambda": 0.01363366782252473,
}


@dataclass(frozen=True)
class PriceModelConfig:
    """Configuration for reproducible local price-model retraining."""

    model_task: str = "price_prediction"
    target_column: str = "log_price"
    price_column: str = "price"
    random_seed: int = 42
    test_size: float = 0.2
    n_splits: int = 5
    primary_metric: str = "rmse"
    secondary_metrics: tuple[str, ...] = ("mae", "r2", "adjusted_r2")
    feature_set_version: str = "selected_v1"
    selected_features: tuple[str, ...] = SELECTED_FEATURES
    champion_algorithm: str = "XGBRegressor"
    best_parameters: dict[str, object] = field(default_factory=lambda: BEST_XGB_PARAMETERS.copy())
    training_mode: TrainingMode = "retrain"
    artifact_root: str = str(PRICE_ARTIFACTS_DIR)
    output_root: str = str(PRICE_OUTPUTS_DIR)
    run_error_analysis: bool = True
    run_explainability: bool = True
    shap_sample_size: int = 1000
    shap_random_state: int = 42
    xgb_n_estimators: int = 1007
    n_jobs: int = -1
