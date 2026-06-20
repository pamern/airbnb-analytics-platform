"""Asset jobs intentionally omit schedules and sensors."""

from dagster import AssetSelection, define_asset_job

price_retraining_job = define_asset_job("price_retraining_job", selection=AssetSelection.keys(["gold", "gold_price_model_features"], "price_training_result", "price_model_artifact", "price_registry_records", "gold_price_predictions"))
segmentation_retraining_job = define_asset_job("segmentation_retraining_job", selection=AssetSelection.keys(["gold", "gold_cluster_model_features"], "segmentation_training_result", "segmentation_model_artifact", "segmentation_registry_records", "gold_listing_segments", "gold_segment_profiles"))
price_prediction_job = define_asset_job("price_prediction_job", selection=AssetSelection.keys(["gold", "gold_price_model_features"], "current_price_champion", "price_batch_predictions", "write_price_batch_predictions"))
segmentation_assignment_job = define_asset_job("segmentation_assignment_job", selection=AssetSelection.keys(["gold", "gold_cluster_model_features"], "current_segmentation_champion", "segmentation_assignments", "write_segmentation_assignments"))
