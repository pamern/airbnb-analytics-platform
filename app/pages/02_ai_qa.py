from __future__ import annotations

from components.ai_chat import render_ai_chat_page
from components.ui import render_page_header

render_page_header(
    title="AI Q&A",
    subtitle="Đặt câu hỏi về dữ liệu, dashboard và model dự báo giá.",
)
render_ai_chat_page()
