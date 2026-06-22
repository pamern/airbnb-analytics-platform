"""Non-ML Dagster jobs for ingestion, analytics builds and Champion-only refreshes."""

from dagster import AssetSelection, define_asset_job


bronze_ingestion_selection = AssetSelection.groups("ingestion")
dbt_analytics_selection = AssetSelection.groups("analytics")
price_inference_selection = AssetSelection.keys("current_price_champion", "price_batch_predictions", "write_price_batch_predictions")
segmentation_inference_selection = AssetSelection.keys("current_segmentation_champion", "segmentation_assignments", "write_segmentation_assignments")

bronze_ingestion_job = define_asset_job("bronze_ingestion_job", selection=bronze_ingestion_selection)
dbt_analytics_build_job = define_asset_job("dbt_analytics_build_job", selection=dbt_analytics_selection)
data_refresh_selection = bronze_ingestion_selection | dbt_analytics_selection | price_inference_selection | segmentation_inference_selection
data_refresh_job = define_asset_job("data_refresh_job", selection=data_refresh_selection)
