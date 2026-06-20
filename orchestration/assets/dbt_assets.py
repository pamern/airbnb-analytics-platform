"""Manifest-backed dbt assets for the two ML Gold feature models."""

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from orchestration.resources.dbt import dbt_project


@dbt_assets(
    manifest=dbt_project.manifest_path,
    select="gold_price_model_features gold_cluster_model_features",
)
def airbnb_gold_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build only the dbt Gold models required by the ML pipelines."""
    yield from dbt.cli(["build"], context=context).stream()
