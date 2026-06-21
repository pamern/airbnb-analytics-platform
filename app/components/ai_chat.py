from __future__ import annotations

import streamlit as st

QUICK_PROMPTS = [
    "Tóm tắt thị trường Airbnb theo neighbourhood",
    "Giải thích model dự báo giá đang dùng feature nào",
    "Đề xuất insight nên đưa vào dashboard",
]

_WELCOME = (
    "Chào bạn! Mình có thể hỗ trợ giải thích KPI, kết quả model và "
    "gợi ý insight cho dashboard Airbnb Bangkok."
)

_STUB_REPLY = (
    "UI đã nhận câu hỏi. Backend LLM chưa được gắn vào component này — "
    "đây là câu trả lời mẫu. Khi có module trong llm/, "
    "hàm này sẽ gọi insight generator hoặc LLM API."
)


def render_ai_chat_page() -> None:
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = [{"role": "assistant", "content": _WELCOME}]

    # quick prompt buttons
    st.write("**Gợi ý câu hỏi:**")
    cols = st.columns(len(QUICK_PROMPTS))
    for col, prompt_text in zip(cols, QUICK_PROMPTS):
        if col.button(prompt_text, use_container_width=True):
            st.session_state.ai_messages.append({"role": "user", "content": prompt_text})
            st.session_state.ai_messages.append({"role": "assistant", "content": _STUB_REPLY})
            st.rerun()

    st.divider()

    # chat history
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # input
    if prompt := st.chat_input("Hỏi về dữ liệu, dashboard hoặc model..."):
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        st.session_state.ai_messages.append({"role": "assistant", "content": _STUB_REPLY})
        st.rerun()
