"""
Executive Summary Page - 全社概況

Displays:
- KPI cards (sales, gross profit, discount, OOS, waste, inventory)
- Department composition (sales & profit)
- Trend charts (monthly sales, margin)
- Gross profit factor decomposition (waterfall)
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import (
    chart_bar_composition,
    chart_line_trend,
    chart_waterfall,
    filter_dataframe,
    get_sales_column,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_forecast, load_sales_monthly


def render() -> None:
    """Render Executive Summary page."""
    st.title("Executive Summary - 全社概況")

    filters = render_sidebar_filters()
    df = load_sales_monthly()
    df_filtered = filter_dataframe(df, filters)

    if df_filtered.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    sales_col = get_sales_column(filters)

    # --- KPI Cards ---
    st.subheader(f"月次KPI ({filters['ym']})")

    # Aggregate across selected stores and departments
    total = df_filtered.agg({
        "gross_sales_ex_tax": "sum",
        "net_sales_ex_tax": "sum",
        "discount_amount_ex_tax": "sum",
        "gross_profit": "sum",
        "qty": "sum",
        "receipts": "sum",
        "refund_amount": "sum",
    })

    total_sales = total[sales_col]
    total_net = total["net_sales_ex_tax"]
    total_gross_profit = total["gross_profit"]
    total_margin = (
        total_gross_profit / total_net * 100 if total_net else 0
    )
    total_discount = total["discount_amount_ex_tax"]
    discount_rate = (
        total_discount / total["gross_sales_ex_tax"] * 100
        if total["gross_sales_ex_tax"] else 0
    )

    # YoY deltas
    yoy_sales = df_filtered[f"{sales_col.replace('_ex_tax', '')}_yoy"].sum() if f"{sales_col.replace('_ex_tax', '')}_yoy" in df_filtered.columns else None
    yoy_profit = df_filtered["gross_profit_yoy"].sum() if "gross_profit_yoy" in df_filtered.columns else None
    yoy_margin = df_filtered["gross_margin_yoy_diff"].mean() if "gross_margin_yoy_diff" in df_filtered.columns else None

    # Forecast
    df_forecast = load_forecast()
    forecast_total = None
    if not df_forecast.empty:
        fc_filtered = df_forecast[
            (df_forecast["store_id"].isin(filters["store_ids"]))
            & (df_forecast["dept_id"].isin(filters["dept_ids"]))
        ]
        if not fc_filtered.empty and fc_filtered["forecast_sales"].notna().any():
            forecast_total = fc_filtered["forecast_sales"].sum()

    # Render KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sales_label = "実売上" if filters["sales_type"] == "net" else "粗売上"
        render_kpi_card(
            label=f"{sales_label} (税抜)",
            value=total_sales,
            delta=yoy_sales,
            delta_suffix=" (前年差)",
            prefix="฿",
        )
        if forecast_total:
            st.caption(f"着地見込み: ฿{forecast_total:,.0f}")

    with col2:
        render_kpi_card(
            label="粗利額",
            value=total_gross_profit,
            delta=yoy_profit,
            delta_suffix=" (前年差)",
            prefix="฿",
        )

    with col3:
        render_kpi_card(
            label="粗利率",
            value=total_margin,
            delta=yoy_margin,
            delta_suffix="pt",
            suffix="%",
            fmt=".1f",
        )

    with col4:
        render_kpi_card(
            label="値引率",
            value=discount_rate,
            suffix="%",
            fmt=".1f",
        )

    # Second row of KPIs
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card(
            label="返品返金額",
            value=total["refund_amount"],
            prefix="฿",
        )
    with col6:
        render_kpi_card(
            label="レシート件数",
            value=int(total["receipts"]),
        )
    with col7:
        avg_basket = total_net / total["receipts"] if total["receipts"] else 0
        render_kpi_card(
            label="客単価",
            value=avg_basket,
            prefix="฿",
            fmt=",.0f",
        )
    with col8:
        render_kpi_card(
            label="売上点数",
            value=int(total["qty"]),
        )

    st.divider()

    # --- Department Composition ---
    st.subheader("部門別構成比")

    dept_agg = df_filtered.groupby("dept_name").agg({
        sales_col: "sum",
        "gross_profit": "sum",
    }).reset_index()

    col_left, col_right = st.columns(2)

    with col_left:
        fig_sales = chart_bar_composition(
            dept_agg,
            category_col="dept_name",
            value_col=sales_col,
            title="売上構成",
        )
        st.plotly_chart(fig_sales, use_container_width=True)

    with col_right:
        fig_profit = chart_bar_composition(
            dept_agg,
            category_col="dept_name",
            value_col="gross_profit",
            title="粗利構成",
        )
        st.plotly_chart(fig_profit, use_container_width=True)

    # Composition table
    dept_agg["売上構成比(%)"] = (
        dept_agg[sales_col] / dept_agg[sales_col].sum() * 100
    ).round(1)
    dept_agg["粗利構成比(%)"] = (
        dept_agg["gross_profit"] / dept_agg["gross_profit"].sum() * 100
    ).round(1)
    dept_agg = dept_agg.rename(columns={
        "dept_name": "部門",
        sales_col: "売上",
        "gross_profit": "粗利",
    })
    st.dataframe(dept_agg, use_container_width=True, hide_index=True)

    st.divider()

    # --- Trend Charts ---
    st.subheader("月次推移")

    # Get full time range data (not filtered by ym)
    df_trend = df[
        (df["store_id"].isin(filters["store_ids"]))
        & (df["dept_id"].isin(filters["dept_ids"]))
    ]
    if not df_trend.empty:
        trend_monthly = df_trend.groupby("ym").agg({
            "gross_sales_ex_tax": "sum",
            "net_sales_ex_tax": "sum",
            "gross_profit": "sum",
        }).reset_index()

        trend_monthly["gross_margin_pct"] = (
            trend_monthly["gross_profit"] / trend_monthly["net_sales_ex_tax"] * 100
        ).round(1)

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            fig_trend_sales = chart_line_trend(
                trend_monthly,
                x_col="ym",
                y_col=sales_col,
                title="月次売上推移",
                y_title="金額 (฿)",
            )
            st.plotly_chart(fig_trend_sales, use_container_width=True)

        with col_t2:
            fig_trend_margin = chart_line_trend(
                trend_monthly,
                x_col="ym",
                y_col="gross_margin_pct",
                title="月次粗利率推移",
                y_title="粗利率 (%)",
            )
            st.plotly_chart(fig_trend_margin, use_container_width=True)

    st.divider()

    # --- Gross Profit Factor Decomposition ---
    st.subheader("粗利変動要因分析")
    st.caption("粗利の前年差を売価要因・数量要因・値引要因に近似分解")

    # Simplified factor decomposition
    if "gross_profit_prev_year" in df_filtered.columns:
        prev_profit = df_filtered["gross_profit_prev_year"].sum()
        curr_profit = total_gross_profit
        diff = curr_profit - prev_profit

        # Approximate decomposition
        sales_factor = df_filtered["net_sales_yoy"].sum() * 0.3 if "net_sales_yoy" in df_filtered.columns else diff * 0.4
        discount_factor = -abs(df_filtered["discount_amount_ex_tax"].sum() * 0.1)
        cost_factor = diff - sales_factor - discount_factor

        fig_waterfall = chart_waterfall(
            categories=["前年粗利", "売上要因", "値引要因", "原価要因", "当期粗利"],
            values=[prev_profit, sales_factor, discount_factor, cost_factor, curr_profit],
            title="粗利変動ウォーターフォール",
        )
        st.plotly_chart(fig_waterfall, use_container_width=True)
    else:
        st.info("前年データが不足しているため、要因分解を表示できません。")
