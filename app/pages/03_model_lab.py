from __future__ import annotations

from components.model_lab import render_model_lab_page
from components.ui import render_page_header


render_page_header(
    title="Model Performance",
    subtitle="Track model runs, evaluation metrics, registry status and SHAP explanations",
)
render_model_lab_page()
