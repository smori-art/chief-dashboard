"""
Store × Department View - 店舗×部門 クロス分析

Displays:
- Heatmap (stores × departments)
- Problem area detection (margin deterioration, OOS, discount increase)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    chart_heatmap,
    filter_dataframe,
    get_sales_column,
    render_sidebar_filters,
)
from app.data import load_sales_monthly


def render() -> None:
    """Render Store × Department page."""
    st.title("🔀 Store × Department - 店舗×部門分析")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)
    df = load_sales_monthly()
    df_filtered = filter_dataframe(df, filters)

    if df_filtered.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- Heatmap ---
    st.subheader("🗺️ ヒートマップ")

    heatmap_metric = st.radio(
        "表示指標",
        options=["粗利率(%)", "売上前年差", "値引率(%)"],
        horizontal=True,
        key="heatmap_metric",
    )

    # Prepare heatmap data
    cross = df_filtered.groupby(["store_name", "dept_name"]).agg({
        "gross_sales_ex_tax": "sum",
        "net_sales_ex_tax": "sum",
        "gross_profit": "sum",
        "discount_amount_ex_tax": "sum",
        "gross_margin_yoy_diff": "mean",
        "net_sales_yoy": "sum",
    }).reset_index()

    cross["粗利率(%)"] = (
        cross["gross_profit"] / cross["net_sales_ex_tax"] * 100
    ).round(1)
    cross["値引率(%)"] = (
        cross["discount_amount_ex_tax"] / cross["gross_sales_ex_tax"] * 100
    ).round(1)
    cross["売上前年差"] = cross["net_sales_yoy"]

    value_col = heatmap_metric
    color_scale = "RdYlGn" if "粗利" in heatmap_metric else "RdYlBu"

    fig = chart_heatmap(
        cross,
        x_col="dept_name",
        y_col="store_name",
        value_col=value_col,
        title=f"店舗×部門 {heatmap_metric}",
        color_scale=color_scale,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Problem Area Detection ---
    st.subheader("⚠️ 問題箇所の検出")

    # Margin deterioration: YoY diff < -2pt
    st.markdown("**粗利率悪化 (前年比 -2pt以上)**")
    margin_problems = cross[cross["gross_margin_yoy_diff"] < -2].sort_values(
        "gross_margin_yoy_diff"
    )
    if not margin_problems.empty:
        display_margin = margin_problems[[
            "store_name", "dept_name", "粗利率(%)",
            "gross_margin_yoy_diff", "net_sales_ex_tax", "gross_profit",
        ]].rename(columns={
            "store_name": "店舗",
            "dept_name": "部門",
            "gross_margin_yoy_diff": "粗利率前年差(pt)",
            "net_sales_ex_tax": "実売上",
            "gross_profit": "粗利額",
        })
        st.dataframe(display_margin, use_container_width=True, hide_index=True)
    else:
        st.success("粗利率が大幅に悪化している店舗×部門はありません。")

    # High discount rate: > 5%
    st.markdown("**高値引率 (5%以上)**")
    discount_problems = cross[cross["値引率(%)"] > 5].sort_values(
        "値引率(%)", ascending=False
    )
    if not discount_problems.empty:
        display_discount = discount_problems[[
            "store_name", "dept_name", "値引率(%)",
            "discount_amount_ex_tax", "gross_sales_ex_tax",
        ]].rename(columns={
            "store_name": "店舗",
            "dept_name": "部門",
            "discount_amount_ex_tax": "値引額",
            "gross_sales_ex_tax": "粗売上",
        })
        st.dataframe(display_discount, use_container_width=True, hide_index=True)
    else:
        st.success("値引率が特に高い店舗×部門はありません。")

    st.divider()

    # --- Cross Comparison Table ---
    st.subheader("📋 クロス集計テーブル")

    pivot_metric = st.selectbox(
        "指標",
        options=[sales_col, "gross_profit", "粗利率(%)", "値引率(%)"],
        format_func=lambda x: {
            "net_sales_ex_tax": "実売上",
            "gross_sales_ex_tax": "粗売上",
            "gross_profit": "粗利額",
            "粗利率(%)": "粗利率(%)",
            "値引率(%)": "値引率(%)",
        }.get(x, x),
        key="pivot_metric",
    )

    pivot_df = cross.pivot_table(
        index="store_name",
        columns="dept_name",
        values=pivot_metric,
        aggfunc="sum" if pivot_metric in [sales_col, "gross_profit"] else "mean",
    )

    st.dataframe(
        pivot_df.style.format("{:,.0f}" if pivot_metric in [sales_col, "gross_profit"] else "{:.1f}"),
        use_container_width=True,
    )
