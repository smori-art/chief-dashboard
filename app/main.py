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
    :root {
        --accent: #2563EB;
        --accent-light: #DBEAFE;
        --text-primary: #0F172A;
        --text-secondary: #64748B;
        --border: #E2E8F0;
        --surface: #F8FAFC;
        --positive: #16A34A;
        --negative: #DC2626;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #FAFBFD;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stRadio label {
        font-size: 0.85rem;
    }

    /* KPI metric cards */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 14px 18px;
        transition: box-shadow 0.15s ease;
    }
    div[data-testid="stMetric"]:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    div[data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
        font-weight: 700;
        color: var(--text-primary) !important;
    }
    /* Delta colors */
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Up"] {
        fill: var(--positive);
    }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Down"] {
        fill: var(--negative);
    }

    /* Dividers */
    hr {
        border-color: var(--border) !important;
    }

    /* Tables */
    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 6px;
    }

    /* Page title */
    h1 {
        font-weight: 700 !important;
        font-size: 1.5rem !important;
        color: var(--text-primary) !important;
        border-bottom: 2px solid var(--accent);
        padding-bottom: 0.4rem;
    }
    h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }

    /* Expander in sidebar — compact */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {
        font-size: 0.8rem;
        font-weight: 500;
        color: var(--text-secondary);
    }

    /* Navigation labels */
    .nav-category {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-secondary);
        padding: 12px 0 4px 0;
        margin: 0;
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
        "Import / Admin": "app.pages.import_admin",
        "Export / Report": "app.pages.export_report",
    }

    _NAV_GROUPS: list[tuple[str, list[str]]] = [
        ("概況", ["Executive Summary", "Alert Dashboard"]),
        ("切口分析", ["Department View", "Store View", "Store x Department", "Product Analysis"]),
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
                    f"{'● ' if is_active else ''}{label}",
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
