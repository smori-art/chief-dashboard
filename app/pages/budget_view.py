"""
Budget vs Actual Page - 予算対比

Displays:
- Budget vs Actual KPIs
- Progress gauges
- Variance analysis by store/department
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS_GRAY,
    _CHART_LAYOUT,
    filter_dataframe,
    get_sales_column,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_budget_data, load_forecast, load_sales_monthly


def render() -> None:
    """Render Budget vs Actual page."""
    st.title("予実管理")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)

    df_sales = load_sales_monthly()
    df_budget = load_budget_data()
    df_forecast = load_forecast()

    df_sales_f = filter_dataframe(df_sales, filters)
    df_budget_f = filter_dataframe(df_budget, filters)

    if df_sales_f.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- Merge actual and budget ---
    actual_agg = df_sales_f.groupby(["store_id", "dept_id"]).agg({
        "net_sales_ex_tax": "sum",
        "gross_profit": "sum",
    }).reset_index()

    budget_agg = df_budget_f.groupby(["store_id", "dept_id"]).agg({
        "budget_sales": "sum",
        "budget_gross_profit": "sum",
    }).reset_index()

    merged = actual_agg.merge(budget_agg, on=["store_id", "dept_id"], how="outer").fillna(0)
    merged["売上達成率(%)"] = (merged["net_sales_ex_tax"] / merged["budget_sales"] * 100).round(1)
    merged["粗利達成率(%)"] = (merged["net_sales_ex_tax"] / merged["budget_gross_profit"] * 100).round(1)
    merged["売上差異"] = merged["net_sales_ex_tax"] - merged["budget_sales"]
    merged["粗利差異"] = merged["gross_profit"] - merged["budget_gross_profit"]

    # --- Total KPIs ---
    st.subheader("予実サマリ")

    total_actual_sales = merged["net_sales_ex_tax"].sum()
    total_budget_sales = merged["budget_sales"].sum()
    total_actual_profit = merged["gross_profit"].sum()
    total_budget_profit = merged["budget_gross_profit"].sum()
    sales_achieve = total_actual_sales / total_budget_sales * 100 if total_budget_sales else 0
    profit_achieve = total_actual_profit / total_budget_profit * 100 if total_budget_profit else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("実績売上", total_actual_sales, prefix="฿")
    with col2:
        render_kpi_card("予算売上", total_budget_sales, prefix="฿")
    with col3:
        render_kpi_card("売上達成率", sales_achieve, suffix="%", fmt=".1f")
    with col4:
        render_kpi_card("売上差異", total_actual_sales - total_budget_sales, prefix="฿")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card("実績粗利", total_actual_profit, prefix="฿")
    with col6:
        render_kpi_card("予算粗利", total_budget_profit, prefix="฿")
    with col7:
        render_kpi_card("粗利達成率", profit_achieve, suffix="%", fmt=".1f")
    with col8:
        render_kpi_card("粗利差異", total_actual_profit - total_budget_profit, prefix="฿")

    st.divider()

    # --- Progress Gauge ---
    st.subheader("達成率ゲージ")

    # Add forecast if available
    forecast_total = None
    if not df_forecast.empty:
        fc_f = df_forecast[
            (df_forecast["store_id"].isin(filters["store_ids"]))
            & (df_forecast["dept_id"].isin(filters["dept_ids"]))
        ]
        if not fc_f.empty and fc_f["forecast_sales"].notna().any():
            forecast_total = fc_f["forecast_sales"].sum()

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=sales_achieve,
            delta={"reference": 100, "suffix": "%"},
            title={"text": "売上達成率"},
            gauge={
                "axis": {"range": [0, 130]},
                "bar": {"color": "#555"},
                "steps": [
                    {"range": [0, 80], "color": "#e0e0e0"},
                    {"range": [80, 100], "color": "#ccc"},
                    {"range": [100, 130], "color": "#bbb"},
                ],
                "threshold": {"line": {"color": "#333", "width": 3}, "value": 100},
            },
        ))
        fig_gauge.update_layout(height=300, **_CHART_LAYOUT)
        st.plotly_chart(fig_gauge, use_container_width=True)
        if forecast_total:
            fc_achieve = forecast_total / total_budget_sales * 100 if total_budget_sales else 0
            st.caption(f"着地見込み達成率: {fc_achieve:.1f}% (฿{forecast_total:,.0f})")

    with col_g2:
        fig_gauge2 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=profit_achieve,
            delta={"reference": 100, "suffix": "%"},
            title={"text": "粗利達成率"},
            gauge={
                "axis": {"range": [0, 130]},
                "bar": {"color": "#555"},
                "steps": [
                    {"range": [0, 80], "color": "#e0e0e0"},
                    {"range": [80, 100], "color": "#ccc"},
                    {"range": [100, 130], "color": "#bbb"},
                ],
                "threshold": {"line": {"color": "#333", "width": 3}, "value": 100},
            },
        ))
        fig_gauge2.update_layout(height=300, **_CHART_LAYOUT)
        st.plotly_chart(fig_gauge2, use_container_width=True)

    st.divider()

    # --- Store-level variance ---
    st.subheader("店舗別予実差異")

    store_var = merged.groupby("store_id").agg({
        "net_sales_ex_tax": "sum",
        "budget_sales": "sum",
        "gross_profit": "sum",
        "budget_gross_profit": "sum",
    }).reset_index()
    store_var["売上達成率(%)"] = (store_var["net_sales_ex_tax"] / store_var["budget_sales"] * 100).round(1)
    store_var["売上差異"] = store_var["net_sales_ex_tax"] - store_var["budget_sales"]

    fig_var = go.Figure()
    fig_var.add_trace(go.Bar(
        x=store_var["store_id"], y=store_var["budget_sales"],
        name="予算", marker_color="#bbb",
    ))
    fig_var.add_trace(go.Bar(
        x=store_var["store_id"], y=store_var["net_sales_ex_tax"],
        name="実績", marker_color="#555",
    ))
    fig_var.update_layout(
        title="店舗別 予算 vs 実績",
        barmode="group", height=400,
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_var, use_container_width=True)

    st.divider()

    # --- Dept-level variance ---
    st.subheader("部門別予実差異")

    dept_var = merged.groupby("dept_id").agg({
        "net_sales_ex_tax": "sum",
        "budget_sales": "sum",
        "gross_profit": "sum",
        "budget_gross_profit": "sum",
        "売上差異": "sum",
    }).reset_index()
    dept_var["売上達成率(%)"] = (dept_var["net_sales_ex_tax"] / dept_var["budget_sales"] * 100).round(1)
    dept_var = dept_var.rename(columns={
        "dept_id": "部門",
        "net_sales_ex_tax": "実績売上",
        "budget_sales": "予算売上",
        "gross_profit": "実績粗利",
        "budget_gross_profit": "予算粗利",
    })
    st.dataframe(dept_var, use_container_width=True, hide_index=True)
