from __future__ import annotations

from components.dashboard import render_dashboard_page
from components.ui import render_page_header

render_page_header(
    title="Dashboard",
    subtitle="Theo dõi KPI, cấu trúc listing và các lát cắt thị trường từ dbt Gold layer.",
)
render_dashboard_page()
