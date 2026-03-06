"""
Chief Dashboard - Main Streamlit Application Entry Point

Thai Supermarket Monthly Dashboard
タイ食品スーパーマーケット月次ダッシュボード
"""

from __future__ import annotations

import streamlit as st

from app.auth import require_auth, show_user_info_sidebar
from app.config import get_config

_MINIMAL_CSS = """
<style>
    /* --- Gray Minimal Theme --- */
    section[data-testid="stSidebar"] {
        background-color: #f0f0f1;
        border-right: 1px solid #ddd;
    }
    section[data-testid="stSidebar"] .stRadio label {
        font-size: 0.9rem;
    }
    /* KPI metric cards */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label {
        color: #666 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 600;
        color: #1a1a1a !important;
    }
    /* Subdued dividers */
    hr {
        border-color: #e5e5e5 !important;
    }
    /* Table styling */
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }
    /* Page title */
    h1 {
        font-weight: 700 !important;
        font-size: 1.6rem !important;
        color: #222 !important;
        border-bottom: 2px solid #ddd;
        padding-bottom: 0.4rem;
    }
    h2, h3 {
        color: #333 !important;
        font-weight: 600 !important;
    }
    /* Subtle subheaders */
    .stSubheader {
        color: #444 !important;
    }
</style>
"""


def setup_page() -> None:
    """Configure Streamlit page settings."""
    config = get_config()
    st.set_page_config(
        page_title=config.app_title,
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_MINIMAL_CSS, unsafe_allow_html=True)


def main() -> None:
    """Main application entry point."""
    setup_page()

    # Authentication gate
    user = require_auth()
    if user is None:
        return

    # Show user info in sidebar
    show_user_info_sidebar()

    # Navigation
    with st.sidebar:
        st.divider()
        page = st.radio(
            "ページ選択",
            options=[
                "Executive Summary",
                "Department View",
                "Store View",
                "Store × Department",
                "Product Analysis",
                "OOS Analysis",
                "Import / Admin",
                "Export / Report",
            ],
            key="nav_page",
        )

    # Route to selected page
    if page == "Executive Summary":
        from app.pages.executive_summary import render

        render()
    elif page == "Department View":
        from app.pages.department_view import render

        render()
    elif page == "Store View":
        from app.pages.store_view import render

        render()
    elif page == "Store × Department":
        from app.pages.store_dept_view import render

        render()
    elif page == "Product Analysis":
        from app.pages.product_view import render

        render()
    elif page == "OOS Analysis":
        from app.pages.oos_analysis import render

        render()
    elif page == "Import / Admin":
        from app.pages.import_admin import render

        render()
    elif page == "Export / Report":
        from app.pages.export_report import render

        render()


if __name__ == "__main__":
    main()
