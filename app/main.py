"""
Chief Dashboard - Main Streamlit Application Entry Point

Thai Supermarket Monthly Dashboard
タイ食品スーパーマーケット月次ダッシュボード
"""

from __future__ import annotations

import streamlit as st

from app.auth import require_auth, show_user_info_sidebar
from app.config import get_config


def setup_page() -> None:
    """Configure Streamlit page settings."""
    config = get_config()
    st.set_page_config(
        page_title=config.app_title,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )


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
