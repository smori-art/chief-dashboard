"""
Store View Page - 店舗分析

Displays:
- Store KPI comparison table
- Best/Worst rankings
- Store trend comparison
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import (
    chart_line_trend,
    filter_dataframe,
    get_sales_column,
    render_sidebar_filters,
)
from app.data import load_sales_monthly


def render() -> None:
    """Render Store View page."""
    st.title("🏪 Store View - 店舗分析")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)
    df = load_sales_monthly()

    df_filtered = filter_dataframe(df, filters)

    if df_filtered.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- Store KPI Comparison Table ---
    st.subheader("📊 店舗別KPI比較")

    store_agg = df_filtered.groupby(["store_id", "store_name"]).agg({
        "gross_sales_ex_tax": "sum",
        "net_sales_ex_tax": "sum",
        "discount_amount_ex_tax": "sum",
        "gross_profit": "sum",
        "receipts": "sum",
        "qty": "sum",
        "gross_sales_yoy": "sum",
        "net_sales_yoy": "sum",
        "gross_profit_yoy": "sum",
    }).reset_index()

    store_agg["粗利率(%)"] = (
        store_agg["gross_profit"] / store_agg["net_sales_ex_tax"] * 100
    ).round(1)
    store_agg["客単価"] = (
        store_agg["net_sales_ex_tax"] / store_agg["receipts"]
    ).round(0)
    store_agg["値引率(%)"] = (
        store_agg["discount_amount_ex_tax"] / store_agg["gross_sales_ex_tax"] * 100
    ).round(1)
    store_agg["売上前年差"] = store_agg[
        "net_sales_yoy" if sales_col == "net_sales_ex_tax" else "gross_sales_yoy"
    ]
    store_agg["売上前年比(%)"] = (
        (store_agg[sales_col] / (store_agg[sales_col] - store_agg["売上前年差"])) * 100
    ).round(1)

    display_df = store_agg[[
        "store_name", sales_col, "gross_profit", "粗利率(%)",
        "receipts", "客単価", "値引率(%)", "売上前年差", "売上前年比(%)",
    ]].rename(columns={
        "store_name": "店舗",
        sales_col: "売上",
        "gross_profit": "粗利額",
        "receipts": "客数",
    })

    st.dataframe(
        display_df.sort_values("売上", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # --- Best/Worst Rankings ---
    st.subheader("🏆 ベスト / ワースト")

    col_best, col_worst = st.columns(2)

    with col_best:
        st.markdown("**売上伸び率 Top5**")
        top5 = store_agg.nlargest(5, "売上前年比(%)")[
            ["store_name", sales_col, "売上前年比(%)"]
        ].rename(columns={"store_name": "店舗", sales_col: "売上"})
        st.dataframe(top5, use_container_width=True, hide_index=True)

        st.markdown("**粗利率 Top5**")
        top5_margin = store_agg.nlargest(5, "粗利率(%)")[
            ["store_name", "粗利率(%)", "gross_profit"]
        ].rename(columns={"store_name": "店舗", "gross_profit": "粗利額"})
        st.dataframe(top5_margin, use_container_width=True, hide_index=True)

    with col_worst:
        st.markdown("**売上伸び率 Bottom5**")
        bottom5 = store_agg.nsmallest(5, "売上前年比(%)")[
            ["store_name", sales_col, "売上前年比(%)"]
        ].rename(columns={"store_name": "店舗", sales_col: "売上"})
        st.dataframe(bottom5, use_container_width=True, hide_index=True)

        st.markdown("**粗利率 Bottom5**")
        bottom5_margin = store_agg.nsmallest(5, "粗利率(%)")[
            ["store_name", "粗利率(%)", "gross_profit"]
        ].rename(columns={"store_name": "店舗", "gross_profit": "粗利額"})
        st.dataframe(bottom5_margin, use_container_width=True, hide_index=True)

    st.divider()

    # --- Store Trend Comparison ---
    st.subheader("📈 店舗別月次推移")

    # Get full time-range data
    df_trend = df[
        (df["store_id"].isin(filters["store_ids"]))
        & (df["dept_id"].isin(filters["dept_ids"]))
    ]

    if df_trend.empty:
        st.info("トレンドデータがありません。")
        return

    trend_agg = df_trend.groupby(["ym", "store_name"]).agg({
        sales_col: "sum",
        "gross_profit": "sum",
        "net_sales_ex_tax": "sum",
    }).reset_index()

    trend_agg["粗利率(%)"] = (
        trend_agg["gross_profit"] / trend_agg["net_sales_ex_tax"] * 100
    ).round(1)

    # Select stores to compare
    all_stores = sorted(trend_agg["store_name"].unique().tolist())
    compare_stores = st.multiselect(
        "比較する店舗を選択",
        options=all_stores,
        default=all_stores[:4],
        key="store_compare",
    )

    if compare_stores:
        trend_compare = trend_agg[trend_agg["store_name"].isin(compare_stores)]

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            fig = chart_line_trend(
                trend_compare,
                x_col="ym",
                y_col=sales_col,
                color_col="store_name",
                title="売上推移",
                y_title="金額 (฿)",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_t2:
            fig2 = chart_line_trend(
                trend_compare,
                x_col="ym",
                y_col="粗利率(%)",
                color_col="store_name",
                title="粗利率推移",
                y_title="粗利率 (%)",
            )
            st.plotly_chart(fig2, use_container_width=True)
