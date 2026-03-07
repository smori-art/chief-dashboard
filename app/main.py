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
    /* ===== Cool Minimal Theme ===== */

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] .stRadio label {
        font-size: 0.85rem;
    }

    /* KPI metric cards (st.metric fallback + custom HTML cards) */
    div[data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        padding: 16px 20px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    div[data-testid="stMetric"] label {
        color: #64748B !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    /* Dividers */
    hr {
        border-color: #E2E8F0 !important;
    }

    /* Tables */
    .stDataFrame {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
    }

    /* Page title */
    h1 {
        font-weight: 700 !important;
        font-size: 1.5rem !important;
        color: #0F172A !important;
        border-bottom: 2px solid #9B2335 !important;
        padding-bottom: 0.5rem !important;
    }
    h2 {
        color: #0F172A !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }
    h3 {
        color: #334155 !important;
        font-weight: 600 !important;
    }

    /* Sidebar expander */
    section[data-testid="stSidebar"] details summary {
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: #64748B !important;
    }

    /* Sidebar nav buttons — override Streamlit defaults */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        background: transparent !important;
        border: none !important;
        color: #334155 !important;
        font-size: 0.84rem !important;
        font-weight: 400 !important;
        text-align: left !important;
        padding: 4px 12px !important;
        border-radius: 6px !important;
        justify-content: flex-start !important;
        transition: background 0.1s ease !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background: #F1F5F9 !important;
        color: #0F172A !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: #FDF2F4 !important;
        border: none !important;
        border-left: 3px solid #9B2335 !important;
        color: #9B2335 !important;
        font-size: 0.84rem !important;
        font-weight: 600 !important;
        text-align: left !important;
        padding: 4px 12px !important;
        border-radius: 0 6px 6px 0 !important;
        justify-content: flex-start !important;
    }

    /* Nav category labels */
    .nav-category {
        font-size: 0.62rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        color: #94A3B8 !important;
        padding: 14px 0 2px 4px !important;
        margin: 0 !important;
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

    # Navigation — grouped by category
    _PAGE_MAP = {
        "Executive Summary": "app.pages.executive_summary",
        "Alert Dashboard": "app.pages.alert_view",
        "Department View": "app.pages.department_view",
        "Store View": "app.pages.store_view",
        "Store x Department": "app.pages.store_dept_view",
        "Product Analysis": "app.pages.product_view",
        "Timeband Analysis": "app.pages.timeband_view",
        "Daily Trend": "app.pages.daily_trend_view",
        "Basket Analysis": "app.pages.basket_view",
        "Discount Analysis": "app.pages.discount_view",
        "Waste Analysis": "app.pages.waste_view",
        "Budget vs Actual": "app.pages.budget_view",
        "OOS Analysis": "app.pages.oos_analysis",
        "Store PL": "app.pages.store_pl_view",
        "Import / Admin": "app.pages.import_admin",
        "Export / Report": "app.pages.export_report",
    }

    _NAV_GROUPS: list[tuple[str, list[str]]] = [
        ("概況", ["Executive Summary", "Alert Dashboard"]),
        ("切口分析", ["Department View", "Store View", "Store x Department", "Product Analysis", "Store PL"]),
        ("深掘り", ["Timeband Analysis", "Daily Trend", "Basket Analysis",
                   "Discount Analysis", "Waste Analysis", "Budget vs Actual", "OOS Analysis"]),
        ("管理", ["Import / Admin", "Export / Report"]),
    ]

    # Japanese display names for pages
    _PAGE_LABELS = {
        "Executive Summary": "全社概況",
        "Alert Dashboard": "アラート",
        "Department View": "部門分析",
        "Store View": "店舗分析",
        "Store x Department": "店舗×部門",
        "Product Analysis": "商品分析",
        "Timeband Analysis": "時間帯分析",
        "Daily Trend": "日次トレンド",
        "Basket Analysis": "買物かご分析",
        "Discount Analysis": "値引分析",
        "Waste Analysis": "ロス分析",
        "Budget vs Actual": "予実管理",
        "OOS Analysis": "欠品分析",
        "Store PL": "店舗別PL",
        "Import / Admin": "インポート",
        "Export / Report": "レポート出力",
    }

    with st.sidebar:
        st.divider()
        # Build flat list for the radio, but render category headers
        all_pages: list[str] = []
        for _group_label, pages in _NAV_GROUPS:
            all_pages.extend(pages)

        # Default to first page
        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = "Executive Summary"

        # Render grouped navigation
        for group_label, pages in _NAV_GROUPS:
            st.markdown(
                f'<p class="nav-category">{group_label}</p>',
                unsafe_allow_html=True,
            )
            for p in pages:
                label = _PAGE_LABELS.get(p, p)
                is_active = st.session_state.get("nav_page") == p
                if st.button(
                    label,
                    key=f"nav_{p}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["nav_page"] = p
                    st.rerun()

    page = st.session_state.get("nav_page", "Executive Summary")

    import importlib
    module = importlib.import_module(_PAGE_MAP[page])
    module.render()


if __name__ == "__main__":
    main()
