"""Explicit configuration for controlled model-registry fallback during inference."""

from dagster import ConfigurableResource


class InferenceConfig(ConfigurableResource):
    """Keep candidate fallback disabled unless a run explicitly enables it."""

    allow_latest_candidate_fallback: bool = False
