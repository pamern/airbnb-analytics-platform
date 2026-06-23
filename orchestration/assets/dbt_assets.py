"""Manifest-backed dbt assets for the Silver and Gold analytics warehouse."""

from dagster import AssetExecutionContext
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from orchestration.resources.dbt import dbt_project


class AnalyticsDbtTranslator(DagsterDbtTranslator):
    """Put the dbt warehouse assets in one reusable Dagster selection group."""

    def get_group_name(self, dbt_resource_props):
        return "analytics"


@dbt_assets(
    manifest=dbt_project.manifest_path,
    # The project contains only Silver and Gold dbt models; ``fqn:*`` keeps this
    # manifest-backed selection resilient to newly added analytics marts.
    select="fqn:*",
    dagster_dbt_translator=AnalyticsDbtTranslator(),
)
def airbnb_analytics_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build Silver and Gold analytics models, including ML feature tables and tests."""
    yield from dbt.cli(
        ["build"],
        context=context,
        target_path=dbt_project.target_path,
    ).stream()


# Preserve the object name consumed by the four existing ML-job definitions.
airbnb_gold_dbt_assets = airbnb_analytics_dbt_assets
