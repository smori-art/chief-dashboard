"""
Daily Trend Page - 曜日・日別トレンド

Displays:
- Daily sales trend (90 days)
- Day-of-week pattern analysis
- Store × DOW heatmap
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
from app.data import load_daily_sales


def render() -> None:
    """Render Daily Trend page."""
    st.title("Daily Trend - 日別トレンド")

    filters = render_sidebar_filters()
    df = load_daily_sales()

    if filters.get("store_ids"):
        df = df[df["store_id"].isin(filters["store_ids"])]
    if filters.get("dept_ids"):
        df = df[df["dept_id"].isin(filters["dept_ids"])]

    if df.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- KPI Summary ---
    st.subheader("直近90日概況")

    daily_total = df.groupby("date")["net_sales"].sum()
    avg_daily = daily_total.mean()
    max_day = daily_total.idxmax()
    min_day = daily_total.idxmin()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("日平均売上", avg_daily, prefix="฿", fmt=",.0f")
    with col2:
        render_kpi_card("最高売上日", str(max_day))
    with col3:
        render_kpi_card("最高売上額", daily_total.max(), prefix="฿", fmt=",.0f")
    with col4:
        render_kpi_card("最低売上日", str(min_day))

    st.divider()

    # --- Daily Sales Trend ---
    st.subheader("日別売上推移")

    daily_agg = df.groupby("date").agg(
        売上=("net_sales", "sum"),
        客数=("receipts", "sum"),
    ).reset_index().sort_values("date")

    # 7-day moving average
    daily_agg["7日移動平均"] = daily_agg["売上"].rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily_agg["date"], y=daily_agg["売上"],
        marker_color="#ccc", name="日次売上",
    ))
    fig.add_trace(go.Scatter(
        x=daily_agg["date"], y=daily_agg["7日移動平均"],
        mode="lines", line=dict(color="#444", width=2.5),
        name="7日移動平均",
    ))
    fig.update_layout(
        height=400, showlegend=True,
        legend=dict(orientation="h", y=1.12),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- DOW Pattern ---
    st.subheader("曜日別パターン")

    dow_order = ["月", "火", "水", "木", "金", "土", "日"]
    dow_agg = df.groupby("dow_name").agg(
        平均売上=("net_sales", "mean"),
        平均客数=("receipts", "mean"),
        平均点数=("qty", "mean"),
    ).reset_index()
    dow_agg["dow_name"] = pd.Categorical(dow_agg["dow_name"], categories=dow_order, ordered=True)
    dow_agg = dow_agg.sort_values("dow_name")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        fig_dow = go.Figure()
        fig_dow.add_trace(go.Bar(
            x=dow_agg["dow_name"], y=dow_agg["平均売上"],
            marker_color=["#444" if d in ["土", "日"] else "#999" for d in dow_agg["dow_name"]],
        ))
        fig_dow.update_layout(
            title="曜日別平均売上", height=350, **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_dow, use_container_width=True)

    with col_d2:
        fig_traffic = go.Figure()
        fig_traffic.add_trace(go.Bar(
            x=dow_agg["dow_name"], y=dow_agg["平均客数"],
            marker_color=["#444" if d in ["土", "日"] else "#999" for d in dow_agg["dow_name"]],
        ))
        fig_traffic.update_layout(
            title="曜日別平均客数", height=350, **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_traffic, use_container_width=True)

    # DOW stats table
    dow_agg_display = dow_agg.rename(columns={"dow_name": "曜日"})
    dow_agg_display["平均売上"] = dow_agg_display["平均売上"].round(0)
    dow_agg_display["平均客数"] = dow_agg_display["平均客数"].round(0)
    dow_agg_display["平均客単価"] = (dow_agg_display["平均売上"] / dow_agg_display["平均客数"]).round(0)
    st.dataframe(dow_agg_display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Store × DOW Heatmap ---
    st.subheader("店舗 x 曜日 ヒートマップ")

    store_dow = df.groupby(["store_name", "dow_name"])["net_sales"].mean().reset_index()
    fig_hm = chart_heatmap(
        store_dow,
        x_col="dow_name",
        y_col="store_name",
        value_col="net_sales",
        title="店舗 x 曜日 平均売上",
        color_scale="Greys",
    )
    st.plotly_chart(fig_hm, use_container_width=True)
