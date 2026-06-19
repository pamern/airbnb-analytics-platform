from __future__ import annotations

from components.model_lab import render_model_lab_page
from components.ui import render_page_header


render_page_header(
    title="Model Lab",
    subtitle="Theo dõi artifact model, chạy prediction và chuẩn bị workspace cho cluster/model tiếp theo.",
)
render_model_lab_page()
