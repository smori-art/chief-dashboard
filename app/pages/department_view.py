"""
Department View Page - 部門分析

Displays:
- Department-level KPIs
- Category drilldown (大分類 → 中分類 → 小分類)
- Gross margin worst ranking
- Discount rate ranking
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    chart_bar_composition,
    filter_dataframe,
    get_sales_column,
    render_data_table,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_category_drilldown, load_sales_monthly


def render() -> None:
    """Render Department View page."""
    st.title("Department View - 部門分析")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)

    # Load data
    df_sales = load_sales_monthly()
    df_category = load_category_drilldown()

    df_sales_f = filter_dataframe(df_sales, filters)
    df_cat_f = filter_dataframe(df_category, filters)

    if df_sales_f.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # Department selector (tabs)
    dept_names = sorted(df_sales_f["dept_name"].unique().tolist())
    if not dept_names:
        st.warning("部門データがありません。")
        return

    selected_dept = st.selectbox(
        "部門を選択",
        options=dept_names,
        key="dept_select",
    )

    # Get dept_id for selected department
    dept_row = df_sales_f[df_sales_f["dept_name"] == selected_dept].iloc[0]
    dept_id = dept_row["dept_id"]

    # Filter to selected department
    df_dept = df_sales_f[df_sales_f["dept_id"] == dept_id]
    df_cat_dept = df_cat_f[df_cat_f["dept_id"] == dept_id] if not df_cat_f.empty else pd.DataFrame()

    # --- Department KPIs ---
    st.subheader(f"{selected_dept} - KPI")

    dept_totals = df_dept.agg({
        "gross_sales_ex_tax": "sum",
        "net_sales_ex_tax": "sum",
        "discount_amount_ex_tax": "sum",
        "gross_profit": "sum",
        "qty": "sum",
    })

    dept_margin = (
        dept_totals["gross_profit"] / dept_totals["net_sales_ex_tax"] * 100
        if dept_totals["net_sales_ex_tax"] else 0
    )
    dept_discount_rate = (
        dept_totals["discount_amount_ex_tax"] / dept_totals["gross_sales_ex_tax"] * 100
        if dept_totals["gross_sales_ex_tax"] else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("売上", dept_totals[sales_col], prefix="฿")
    with col2:
        render_kpi_card("粗利額", dept_totals["gross_profit"], prefix="฿")
    with col3:
        render_kpi_card("粗利率", dept_margin, suffix="%", fmt=".1f")
    with col4:
        render_kpi_card("値引率", dept_discount_rate, suffix="%", fmt=".1f")

    st.divider()

    # --- Category Drilldown ---
    st.subheader("カテゴリ別ドリルダウン")

    if df_cat_dept.empty:
        st.info("カテゴリデータがありません。")
    else:
        # Drilldown level selector
        drill_level = st.radio(
            "表示レベル",
            options=["大分類", "中分類", "小分類"],
            horizontal=True,
            key="drill_level",
        )

        if drill_level == "大分類":
            group_cols = ["cat_l"]
            display_cols = {"cat_l": "大分類"}
        elif drill_level == "中分類":
            group_cols = ["cat_l", "cat_m"]
            display_cols = {"cat_l": "大分類", "cat_m": "中分類"}
        else:
            group_cols = ["cat_l", "cat_m", "cat_s"]
            display_cols = {"cat_l": "大分類", "cat_m": "中分類", "cat_s": "小分類"}

        cat_agg = df_cat_dept.groupby(group_cols).agg({
            "gross_sales_ex_tax": "sum",
            "net_sales_ex_tax": "sum",
            "discount_amount_ex_tax": "sum",
            "gross_profit": "sum",
            "qty": "sum",
        }).reset_index()

        cat_agg["粗利率(%)"] = (
            cat_agg["gross_profit"] / cat_agg["net_sales_ex_tax"] * 100
        ).round(1)
        cat_agg["値引率(%)"] = (
            cat_agg["discount_amount_ex_tax"] / cat_agg["gross_sales_ex_tax"] * 100
        ).round(1)

        # Rename for display
        cat_display = cat_agg.rename(columns={
            **display_cols,
            "gross_sales_ex_tax": "粗売上",
            "net_sales_ex_tax": "実売上",
            "discount_amount_ex_tax": "値引額",
            "gross_profit": "粗利額",
            "qty": "数量",
        })

        # Sort by gross margin ascending (worst first)
        cat_display = cat_display.sort_values("粗利率(%)", ascending=True)

        st.dataframe(
            cat_display,
            use_container_width=True,
            hide_index=True,
            height=min(400, max(200, len(cat_display) * 35 + 50)),
        )

    st.divider()

    # --- Rankings ---
    st.subheader("ランキング")

    if not df_cat_dept.empty:
        col_r1, col_r2 = st.columns(2)

        with col_r1:
            st.markdown("**粗利率ワースト Top10**")
            worst_margin = df_cat_dept.nsmallest(10, "gross_margin_pct")[
                ["cat_l", "cat_m", "cat_s", "gross_margin_pct", "net_sales_ex_tax", "gross_profit"]
            ].rename(columns={
                "cat_l": "大分類",
                "cat_m": "中分類",
                "cat_s": "小分類",
                "gross_margin_pct": "粗利率(%)",
                "net_sales_ex_tax": "実売上",
                "gross_profit": "粗利額",
            })
            st.dataframe(worst_margin, use_container_width=True, hide_index=True)

        with col_r2:
            st.markdown("**値引率ワースト Top10**")
            worst_discount = df_cat_dept.nlargest(10, "discount_rate_pct")[
                ["cat_l", "cat_m", "cat_s", "discount_rate_pct", "gross_sales_ex_tax", "discount_amount_ex_tax"]
            ].rename(columns={
                "cat_l": "大分類",
                "cat_m": "中分類",
                "cat_s": "小分類",
                "discount_rate_pct": "値引率(%)",
                "gross_sales_ex_tax": "粗売上",
                "discount_amount_ex_tax": "値引額",
            })
            st.dataframe(worst_discount, use_container_width=True, hide_index=True)
    else:
        st.info("ランキング表示にはカテゴリデータが必要です。")
