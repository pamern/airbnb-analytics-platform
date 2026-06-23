from __future__ import annotations

from app.components.dashboard import render_dashboard_page
from app.components.ui import render_page_header

render_page_header(
    title="Dashboard",
    subtitle="Track KPIs, listing structure, and market slices from the dbt Gold layer.",
)
render_dashboard_page()
