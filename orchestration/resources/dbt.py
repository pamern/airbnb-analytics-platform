"""Repository-relative Dagster dbt resource configuration."""

from dagster_dbt import DbtCliResource, DbtProject

from ml.common.paths import REPO_ROOT

DBT_PROJECT_DIR = REPO_ROOT / "dbt"
dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
)
dbt_project.prepare_if_dev()


def build_dbt_resource() -> DbtCliResource:
    """Build a dbt CLI resource without invoking dbt at import time."""
    return DbtCliResource(project_dir=dbt_project)
