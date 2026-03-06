"""
Waste / Loss Analysis Page - ロス・廃棄分析

Displays:
- Waste KPIs (total, rate)
- Waste type breakdown
- Department comparison
- Store comparison
- Monthly trend
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS_GRAY,
    _CHART_LAYOUT,
    chart_heatmap,
    chart_line_trend,
    filter_dataframe,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_waste_data


def render() -> None:
    """Render Waste/Loss Analysis page."""
    st.title("Waste Analysis - ロス・廃棄分析")

    filters = render_sidebar_filters()
    df = load_waste_data()

    df_f = filter_dataframe(df, filters)

    if df_f.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- KPI Summary ---
    st.subheader("ロス概況")

    total_waste = df_f["waste_amount"].sum()
    total_sales = df_f["dept_sales"].sum()
    overall_rate = total_waste / total_sales * 100 if total_sales else 0
    total_qty = df_f["waste_qty"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("ロス総額", total_waste, prefix="฿")
    with col2:
        render_kpi_card("ロス率", overall_rate, suffix="%", fmt=".2f")
    with col3:
        render_kpi_card("ロス点数", int(total_qty), fmt=",d")
    with col4:
        render_kpi_card("対象売上", total_sales, prefix="฿")

    st.divider()

    # --- Waste Type Breakdown ---
    st.subheader("ロス種別内訳")

    type_agg = df_f.groupby("waste_type").agg(
        ロス額=("waste_amount", "sum"),
        ロス点数=("waste_qty", "sum"),
    ).reset_index().sort_values("ロス額", ascending=False)
    type_agg["構成比(%)"] = (type_agg["ロス額"] / type_agg["ロス額"].sum() * 100).round(1)

    col_t1, col_t2 = st.columns([1, 1])

    with col_t1:
        fig_pie = go.Figure(go.Pie(
            labels=type_agg["waste_type"],
            values=type_agg["ロス額"],
            marker=dict(colors=COLORS_GRAY),
            textinfo="label+percent",
            hole=0.4,
        ))
        fig_pie.update_layout(
            title="ロス種別構成比",
            height=380, showlegend=False,
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_t2:
        type_display = type_agg.rename(columns={"waste_type": "種別"})
        st.dataframe(type_display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Department Comparison ---
    st.subheader("部門別ロス分析")

    dept_agg = df_f.groupby("dept_name").agg(
        ロス額=("waste_amount", "sum"),
        売上=("dept_sales", "sum"),
        ロス点数=("waste_qty", "sum"),
    ).reset_index()
    dept_agg["ロス率(%)"] = (dept_agg["ロス額"] / dept_agg["売上"] * 100).round(2)
    dept_agg = dept_agg.sort_values("ロス率(%)", ascending=False)

    fig_dept = go.Figure()
    fig_dept.add_trace(go.Bar(
        x=dept_agg["dept_name"], y=dept_agg["ロス額"],
        marker_color="#888", name="ロス額",
    ))
    fig_dept.add_trace(go.Scatter(
        x=dept_agg["dept_name"], y=dept_agg["ロス率(%)"],
        mode="lines+markers", marker=dict(color="#444", size=8),
        line=dict(color="#444", width=2), name="ロス率(%)", yaxis="y2",
    ))
    fig_dept.update_layout(
        title="部門別ロス額・ロス率",
        yaxis=dict(title="ロス額 (฿)"),
        yaxis2=dict(title="ロス率 (%)", overlaying="y", side="right"),
        height=400, showlegend=True,
        legend=dict(orientation="h", y=1.12),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_dept, use_container_width=True)

    st.dataframe(dept_agg, use_container_width=True, hide_index=True)

    st.divider()

    # --- Store Comparison ---
    st.subheader("店舗別ロス比較")

    store_agg = df_f.groupby("store_name").agg(
        ロス額=("waste_amount", "sum"),
        売上=("dept_sales", "sum"),
    ).reset_index()
    store_agg["ロス率(%)"] = (store_agg["ロス額"] / store_agg["売上"] * 100).round(2)
    store_agg = store_agg.sort_values("ロス率(%)", ascending=False)

    fig_store = go.Figure(go.Bar(
        x=store_agg["store_name"], y=store_agg["ロス率(%)"],
        marker_color="#666", text=store_agg["ロス率(%)"],
        textposition="outside", texttemplate="%{text:.2f}%",
    ))
    fig_store.update_layout(
        title="店舗別ロス率",
        height=350, **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_store, use_container_width=True)

    st.divider()

    # --- Store × Dept Heatmap ---
    st.subheader("店舗 x 部門 ロス率")

    store_dept = df_f.groupby(["store_name", "dept_name"]).agg(
        waste=("waste_amount", "sum"),
        sales=("dept_sales", "sum"),
    ).reset_index()
    store_dept["ロス率(%)"] = (store_dept["waste"] / store_dept["sales"] * 100).round(2)

    fig_hm = chart_heatmap(
        store_dept,
        x_col="dept_name",
        y_col="store_name",
        value_col="ロス率(%)",
        title="店舗 x 部門 ロス率 (%)",
        color_scale="Greys",
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    st.divider()

    # --- Monthly Trend ---
    st.subheader("ロス月次推移")

    # Get full time-range data
    df_trend = df.copy()
    if filters.get("store_ids"):
        df_trend = df_trend[df_trend["store_id"].isin(filters["store_ids"])]
    if filters.get("dept_ids"):
        df_trend = df_trend[df_trend["dept_id"].isin(filters["dept_ids"])]

    if not df_trend.empty:
        monthly_agg = df_trend.groupby("ym").agg(
            ロス額=("waste_amount", "sum"),
            売上=("dept_sales", "sum"),
        ).reset_index()
        monthly_agg["ロス率(%)"] = (monthly_agg["ロス額"] / monthly_agg["売上"] * 100).round(2)

        fig_trend = chart_line_trend(
            monthly_agg,
            x_col="ym",
            y_col="ロス率(%)",
            title="ロス率月次推移",
            y_title="ロス率 (%)",
        )
        st.plotly_chart(fig_trend, use_container_width=True)
