from __future__ import annotations

import streamlit as st

from app.data_access import load_pricing_insight_context
from configs.settings import LLM
from llm.groq_insights import generate_airbnb_insights


QUICK_PROMPTS = [
    "Tom tat thi truong Airbnb theo neighbourhood",
    "De xuat 3 insight nen dua vao dashboard",
    "Giai thich pricing va occupancy cho nguoi kinh doanh",
]

_WELCOME = (
    "Chao ban! Page nay demo cach Streamlit lay summary tu Gold layer, "
    "gui sang Groq Llama 3, roi hien insight bang ngon ngu tu nhien."
)


def render_ai_chat_page() -> None:
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = [{"role": "assistant", "content": _WELCOME}]

    st.subheader("Groq insight demo")
    st.caption(
        "Demo nay khong gui raw dataset len LLM. App chi gui bang tom tat ngan "
        "tu Gold pricing data de Llama 3 viet 3 insight."
    )

    if "pricing_insight_context" not in st.session_state:
        st.session_state.pricing_insight_context = ""

    preview_col, clear_col = st.columns([1, 1])
    if preview_col.button("Load data preview", use_container_width=True):
        with st.spinner("Loading compact Gold summary..."):
            try:
                st.session_state.pricing_insight_context = load_pricing_insight_context()
            except Exception as exc:  # pragma: no cover
                st.error(f"Cannot build pricing insight context: {exc}")
    if clear_col.button("Clear cached preview", use_container_width=True):
        st.session_state.pricing_insight_context = ""
        st.cache_data.clear()
        st.rerun()

    with st.expander("Preview data context sent to Groq", expanded=False):
        context = st.session_state.pricing_insight_context
        if context:
            st.markdown(context)
        else:
            st.caption("Click Load data preview, or click Generate to load this context automatically.")

    if st.button("Generate 3 Airbnb insights with Groq", use_container_width=True):
        context = st.session_state.pricing_insight_context
        if not context:
            with st.spinner("Loading compact Gold summary..."):
                try:
                    context = load_pricing_insight_context()
                    st.session_state.pricing_insight_context = context
                except Exception as exc:  # pragma: no cover
                    st.error(f"Cannot build pricing insight context: {exc}")
                    context = ""

        if not context:
            st.warning("No data context is available yet.")
        elif not LLM.groq_api_key.strip():
            st.warning("Missing GROQ_API_KEY in .env.")
        elif not LLM.model.strip():
            st.warning("Missing LLM_MODEL in .env, for example llama-3.1-8b-instant.")
        else:
            with st.spinner("Calling Groq and generating insights..."):
                try:
                    answer = generate_airbnb_insights(context)
                except Exception as exc:  # pragma: no cover
                    st.error(f"Groq insight generation failed: {exc}")
                else:
                    st.session_state.ai_messages.append(
                        {
                            "role": "user",
                            "content": "Generate 3 Airbnb insights from Gold pricing data.",
                        }
                    )
                    st.session_state.ai_messages.append(
                        {"role": "assistant", "content": answer}
                    )
                    st.rerun()
    st.divider()
    st.write("**Prompt goi y:**")
    cols = st.columns(len(QUICK_PROMPTS))
    for col, prompt_text in zip(cols, QUICK_PROMPTS):
        if col.button(prompt_text, use_container_width=True):
            st.session_state.ai_messages.append({"role": "user", "content": prompt_text})
            st.session_state.ai_messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "Voi ban demo chac an, hay bam nut Generate o tren de app "
                        "lay summary tu Gold layer va goi Groq. O chat tu do nay "
                        "co the mo rong sau neu con thoi gian."
                    ),
                }
            )
            st.rerun()

    st.divider()

    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Hoi ve insight, dashboard hoac cach demo Groq..."):
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        st.session_state.ai_messages.append(
            {
                "role": "assistant",
                "content": (
                    "Ban nay dang uu tien insight generator thay vi chatbot tu do. "
                    "Neu can tra loi cau hoi nay bang Groq, ta co the dung cung "
                    "data context o tren va gui prompt tuy bien."
                ),
            }
        )
        st.rerun()
