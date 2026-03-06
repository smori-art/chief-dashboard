"""
Timeband Analysis Page - 時間帯別売上分析

Displays:
- Timeband × Department heatmap
- Peak hour identification
- Store comparison by timeband
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS_GRAY,
    _CHART_LAYOUT,
    chart_heatmap,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_timeband_data


def render() -> None:
    """Render Timeband Analysis page."""
    st.title("Timeband Analysis - 時間帯別分析")

    filters = render_sidebar_filters()
    df = load_timeband_data()

    # Apply filters
    if filters.get("store_ids"):
        df = df[df["store_id"].isin(filters["store_ids"])]
    if filters.get("dept_ids"):
        df = df[df["dept_id"].isin(filters["dept_ids"])]

    if df.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- KPI Summary ---
    st.subheader("時間帯別概況")

    total_sales = df["net_sales"].sum()
    peak_tb = df.groupby("timeband")["net_sales"].sum().idxmax()
    peak_sales = df.groupby("timeband")["net_sales"].sum().max()
    peak_ratio = peak_sales / total_sales * 100 if total_sales else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        render_kpi_card("総売上", total_sales, prefix="฿")
    with col2:
        render_kpi_card("ピーク時間帯", peak_tb)
    with col3:
        render_kpi_card("ピーク構成比", peak_ratio, suffix="%", fmt=".1f")

    st.divider()

    # --- Timeband × Department Heatmap ---
    st.subheader("時間帯 x 部門 売上ヒートマップ")

    heatmap_data = df.groupby(["dept_name", "timeband"])["net_sales"].sum().reset_index()
    fig_hm = chart_heatmap(
        heatmap_data,
        x_col="timeband",
        y_col="dept_name",
        value_col="net_sales",
        title="時間帯 x 部門 売上",
        color_scale="Greys",
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    st.divider()

    # --- Hourly Sales Distribution ---
    st.subheader("時間帯別売上分布")

    tb_agg = df.groupby("timeband").agg(
        売上=("net_sales", "sum"),
        客数=("receipts", "sum"),
        点数=("qty", "sum"),
    ).reset_index()
    tb_agg["客単価"] = (tb_agg["売上"] / tb_agg["客数"]).round(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tb_agg["timeband"], y=tb_agg["売上"],
        marker_color="#666", name="売上",
    ))
    fig.add_trace(go.Scatter(
        x=tb_agg["timeband"], y=tb_agg["客数"],
        mode="lines+markers", marker=dict(color="#999", size=6),
        line=dict(color="#999", width=2), name="客数", yaxis="y2",
    ))
    fig.update_layout(
        yaxis=dict(title="売上 (฿)"),
        yaxis2=dict(title="客数", overlaying="y", side="right"),
        height=400, showlegend=True,
        legend=dict(orientation="h", y=1.12),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- DOW × Timeband Pattern ---
    st.subheader("曜日 x 時間帯パターン")

    dow_names = {1: "月", 2: "火", 3: "水", 4: "木", 5: "金", 6: "土", 7: "日"}
    df["dow_name"] = df["dow"].map(dow_names)
    dow_tb = df.groupby(["dow_name", "timeband"])["net_sales"].mean().reset_index()

    fig_dow = chart_heatmap(
        dow_tb,
        x_col="timeband",
        y_col="dow_name",
        value_col="net_sales",
        title="曜日 x 時間帯 平均売上",
        color_scale="Greys",
    )
    st.plotly_chart(fig_dow, use_container_width=True)

    st.divider()

    # --- Store Comparison ---
    st.subheader("店舗別ピーク時間帯")

    store_tb = df.groupby(["store_id", "timeband"])["net_sales"].sum().reset_index()
    store_peaks = store_tb.loc[store_tb.groupby("store_id")["net_sales"].idxmax()]
    store_peaks = store_peaks.rename(columns={
        "store_id": "店舗", "timeband": "ピーク時間帯", "net_sales": "ピーク売上",
    })
    st.dataframe(store_peaks, use_container_width=True, hide_index=True)
