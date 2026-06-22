from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from components.ui import inject_global_styles  # noqa: E402


st.set_page_config(
    page_title="Airbnb Analytics Platform",
    page_icon=":material/home:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_pages() -> list[st.Page]:
    return [
        st.Page("pages/01_dashboard.py", title="Dashboard", icon=":material/dashboard:", url_path="dashboard"),
        st.Page("pages/02_ai_qa.py", title="AI Q&A", icon=":material/smart_toy:", url_path="ai-qa"),
        st.Page("pages/03_model_lab.py", title="Model Lab", icon=":material/science:", url_path="model-lab"),
    ]


def render_sidebar(pages: list[st.Page]) -> None:
    with st.sidebar:
        st.markdown("### Airbnb Analytics")
        st.caption("Phân tích thị trường · Dự đoán giá · Trợ lý AI")
        st.divider()
        for page in pages:
            st.page_link(page)
        st.divider()


def main() -> None:
    inject_global_styles()
    pages = get_pages()
    render_sidebar(pages)
    navigation = st.navigation(pages, position="hidden")
    navigation.run()


if __name__ == "__main__":
    main()
