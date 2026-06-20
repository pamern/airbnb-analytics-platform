"""Single Dagster Definitions entry point: ``dagster dev -m orchestration.definitions``."""

from dagster import Definitions

from orchestration.assets.dbt_assets import airbnb_gold_dbt_assets
from orchestration.assets.inference_assets import (
    current_price_champion,
    current_segmentation_champion,
    price_batch_predictions,
    segmentation_assignments,
    write_price_batch_predictions,
    write_segmentation_assignments,
)
from orchestration.assets.ml_assets import (
    gold_listing_segments,
    gold_price_predictions,
    gold_segment_profiles,
    price_model_artifact,
    price_registry_records,
    price_training_result,
    segmentation_model_artifact,
    segmentation_registry_records,
    segmentation_training_result,
)
from orchestration.checks.ml_checks import price_prediction_check, price_training_check, segmentation_assignment_check, segmentation_training_check
from orchestration.jobs.ml_jobs import price_prediction_job, price_retraining_job, segmentation_assignment_job, segmentation_retraining_job
from orchestration.resources.dbt import build_dbt_resource
from orchestration.resources.inference import InferenceConfig
from orchestration.resources.motherduck import MotherDuckResource

defs = Definitions(
    assets=[airbnb_gold_dbt_assets, price_training_result, price_model_artifact, price_registry_records, gold_price_predictions, segmentation_training_result, segmentation_model_artifact, segmentation_registry_records, gold_listing_segments, gold_segment_profiles, current_price_champion, price_batch_predictions, write_price_batch_predictions, current_segmentation_champion, segmentation_assignments, write_segmentation_assignments],
    asset_checks=[price_training_check, segmentation_training_check, price_prediction_check, segmentation_assignment_check],
    jobs=[price_retraining_job, price_prediction_job, segmentation_retraining_job, segmentation_assignment_job],
    resources={"motherduck": MotherDuckResource(), "dbt": build_dbt_resource(), "inference_config": InferenceConfig()},
)
