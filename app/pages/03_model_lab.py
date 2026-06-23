from __future__ import annotations

from app.components.model_lab import render_model_lab_page
from app.components.ui import render_page_header


render_page_header(
    title="Model Lab",
    subtitle="Track model artifacts, run prediction inputs, and prepare the next modeling workspace.",
)
render_model_lab_page()
