"""
Discount Analysis Page - 値引分析

Displays:
- Discount breakdown by reason
- Timeband discount pattern (evening spike)
- Store/Department comparison
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
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_discount_detail


def render() -> None:
    """Render Discount Analysis page."""
    st.title("Discount Analysis - 値引分析")

    filters = render_sidebar_filters()
    df = load_discount_detail()

    if filters.get("store_ids"):
        df = df[df["store_id"].isin(filters["store_ids"])]
    if filters.get("dept_ids"):
        df = df[df["dept_id"].isin(filters["dept_ids"])]

    if df.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- KPI Summary ---
    st.subheader("値引概況")

    total_discount = df["discount_amount"].sum()
    total_count = df["discount_count"].sum()
    avg_per_item = total_discount / total_count if total_count else 0
    n_reasons = df["discount_reason"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("値引総額", total_discount, prefix="฿")
    with col2:
        render_kpi_card("値引件数", int(total_count), fmt=",d")
    with col3:
        render_kpi_card("平均値引額", avg_per_item, prefix="฿", fmt=",.0f")
    with col4:
        render_kpi_card("値引理由数", n_reasons, fmt="d")

    st.divider()

    # --- Reason Breakdown ---
    st.subheader("値引理由別内訳")

    reason_agg = df.groupby("discount_reason").agg(
        値引額=("discount_amount", "sum"),
        件数=("discount_count", "sum"),
    ).reset_index().sort_values("値引額", ascending=False)
    reason_agg["構成比(%)"] = (reason_agg["値引額"] / reason_agg["値引額"].sum() * 100).round(1)
    reason_agg["平均値引額"] = (reason_agg["値引額"] / reason_agg["件数"]).round(0)

    col_r1, col_r2 = st.columns([1, 1])

    with col_r1:
        fig_pie = go.Figure(go.Pie(
            labels=reason_agg["discount_reason"],
            values=reason_agg["値引額"],
            marker=dict(colors=COLORS_GRAY),
            textinfo="label+percent",
            hole=0.4,
        ))
        fig_pie.update_layout(
            title="値引理由別構成比",
            height=400, showlegend=False,
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_r2:
        reason_display = reason_agg.rename(columns={"discount_reason": "理由"})
        st.dataframe(reason_display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Timeband Pattern ---
    st.subheader("時間帯別値引パターン")
    st.caption("閉店前の期限間近・見切り品の値引パターンを分析")

    tb_reason = df.groupby(["timeband", "discount_reason"])["discount_amount"].sum().reset_index()

    fig_tb = px.bar(
        tb_reason,
        x="timeband", y="discount_amount", color="discount_reason",
        title="時間帯別 x 理由別 値引額",
        color_discrete_sequence=COLORS_GRAY,
    )
    fig_tb.update_layout(
        height=400,
        xaxis_title="時間帯", yaxis_title="値引額 (฿)",
        legend_title="理由",
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_tb, use_container_width=True)

    st.divider()

    # --- Department Comparison ---
    st.subheader("部門別値引分析")

    dept_agg = df.groupby(["dept_id", "discount_reason"]).agg(
        値引額=("discount_amount", "sum"),
        件数=("discount_count", "sum"),
    ).reset_index()

    dept_total = dept_agg.groupby("dept_id")["値引額"].sum().reset_index()
    dept_total.columns = ["dept_id", "部門値引総額"]
    dept_agg = dept_agg.merge(dept_total, on="dept_id")
    dept_agg["構成比(%)"] = (dept_agg["値引額"] / dept_agg["部門値引総額"] * 100).round(1)

    fig_dept = px.bar(
        dept_agg,
        x="dept_id", y="値引額", color="discount_reason",
        title="部門別 x 理由別 値引額",
        color_discrete_sequence=COLORS_GRAY,
    )
    fig_dept.update_layout(
        height=400,
        xaxis_title="部門", yaxis_title="値引額 (฿)",
        legend_title="理由",
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_dept, use_container_width=True)

    st.divider()

    # --- Store × Reason Heatmap ---
    st.subheader("店舗 x 理由 ヒートマップ")

    store_reason = df.groupby(["store_id", "discount_reason"])["discount_amount"].sum().reset_index()
    fig_hm = chart_heatmap(
        store_reason,
        x_col="discount_reason",
        y_col="store_id",
        value_col="discount_amount",
        title="店舗 x 値引理由",
        color_scale="Greys",
    )
    st.plotly_chart(fig_hm, use_container_width=True)
