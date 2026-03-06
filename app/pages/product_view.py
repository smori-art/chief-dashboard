"""
Product Analysis Page - 商品別分析

Displays:
- Product search and filtering
- Top/Bottom products by sales, margin, discount
- Product trend analysis
- ABC analysis (sales contribution ranking)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    COLORS_GRAY,
    _CHART_LAYOUT,
    chart_bar_composition,
    chart_line_trend,
    filter_dataframe,
    get_sales_column,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_category_drilldown, load_sales_monthly


def render() -> None:
    """Render Product Analysis page."""
    st.title("Product Analysis - 商品別分析")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)

    df_cat = load_category_drilldown()
    df_cat_f = filter_dataframe(df_cat, filters)

    if df_cat_f.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- Product KPI Summary ---
    st.subheader("商品概況")

    total_sales = df_cat_f[sales_col].sum()
    total_profit = df_cat_f["gross_profit"].sum()
    total_margin = (total_profit / df_cat_f["net_sales_ex_tax"].sum() * 100) if df_cat_f["net_sales_ex_tax"].sum() else 0
    unique_products = df_cat_f["cat_s"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("売上合計", total_sales, prefix="฿")
    with col2:
        render_kpi_card("粗利合計", total_profit, prefix="฿")
    with col3:
        render_kpi_card("粗利率", total_margin, suffix="%", fmt=".1f")
    with col4:
        render_kpi_card("商品数 (小分類)", unique_products, fmt=",d")

    st.divider()

    # --- Product Search ---
    search_query = st.text_input(
        "商品名で検索（小分類）",
        placeholder="例: コロッケ, マグロ, 緑茶...",
        key="product_search",
    )

    # --- ABC Analysis ---
    st.subheader("ABC分析 (売上構成比)")

    product_agg = df_cat_f.groupby(["dept_id", "cat_l", "cat_m", "cat_s"]).agg({
        "gross_sales_ex_tax": "sum",
        "net_sales_ex_tax": "sum",
        "discount_amount_ex_tax": "sum",
        "gross_profit": "sum",
        "qty": "sum",
    }).reset_index()

    product_agg["粗利率(%)"] = (
        product_agg["gross_profit"] / product_agg["net_sales_ex_tax"] * 100
    ).round(1)
    product_agg["値引率(%)"] = (
        product_agg["discount_amount_ex_tax"] / product_agg["gross_sales_ex_tax"] * 100
    ).round(1)

    # Apply search filter
    if search_query:
        product_agg = product_agg[
            product_agg["cat_s"].str.contains(search_query, case=False, na=False)
            | product_agg["cat_m"].str.contains(search_query, case=False, na=False)
            | product_agg["cat_l"].str.contains(search_query, case=False, na=False)
        ]

    if product_agg.empty:
        st.info("検索条件に一致する商品がありません。")
        return

    # ABC ranking
    product_ranked = product_agg.sort_values(sales_col, ascending=False).copy()
    product_ranked["売上累積比(%)"] = (
        product_ranked[sales_col].cumsum() / product_ranked[sales_col].sum() * 100
    ).round(1)

    # Assign ABC rank
    product_ranked["ランク"] = product_ranked["売上累積比(%)"].apply(
        lambda x: "A" if x <= 70 else ("B" if x <= 90 else "C")
    )

    # Summary by rank
    rank_summary = product_ranked.groupby("ランク").agg(
        商品数=("cat_s", "nunique"),
        売上=("net_sales_ex_tax", "sum"),
        粗利=("gross_profit", "sum"),
    ).reset_index()
    rank_summary["売上構成比(%)"] = (rank_summary["売上"] / rank_summary["売上"].sum() * 100).round(1)

    col_abc1, col_abc2 = st.columns([1, 2])

    with col_abc1:
        st.dataframe(
            rank_summary.sort_values("ランク"),
            use_container_width=True,
            hide_index=True,
        )

    with col_abc2:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=product_ranked["cat_s"].head(20),
            y=product_ranked[sales_col].head(20),
            marker_color=[
                "#444" if r == "A" else "#888" if r == "B" else "#ccc"
                for r in product_ranked["ランク"].head(20)
            ],
            name="売上",
        ))
        fig.add_trace(go.Scatter(
            x=product_ranked["cat_s"].head(20),
            y=product_ranked["売上累積比(%)"].head(20),
            mode="lines+markers",
            marker=dict(color="#666", size=5),
            line=dict(color="#666", width=2),
            name="累積比(%)",
            yaxis="y2",
        ))
        fig.update_layout(
            title="売上上位20商品 (パレート図)",
            yaxis=dict(title="売上 (฿)"),
            yaxis2=dict(title="累積比 (%)", overlaying="y", side="right", range=[0, 105]),
            height=400,
            showlegend=False,
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Top/Bottom Rankings ---
    st.subheader("商品ランキング")

    rank_metric = st.radio(
        "指標",
        options=["売上", "粗利率", "値引率"],
        horizontal=True,
        key="product_rank_metric",
    )

    col_top, col_bottom = st.columns(2)

    display_cols = {
        "dept_id": "部門",
        "cat_l": "大分類",
        "cat_m": "中分類",
        "cat_s": "小分類",
    }

    with col_top:
        st.markdown("**Top 15**")
        if rank_metric == "売上":
            top = product_ranked.nlargest(15, sales_col)
            show_cols = [*display_cols.keys(), sales_col, "gross_profit", "粗利率(%)"]
        elif rank_metric == "粗利率":
            top = product_ranked.nlargest(15, "粗利率(%)")
            show_cols = [*display_cols.keys(), "粗利率(%)", "net_sales_ex_tax", "gross_profit"]
        else:
            top = product_ranked.nlargest(15, "値引率(%)")
            show_cols = [*display_cols.keys(), "値引率(%)", "discount_amount_ex_tax", "gross_sales_ex_tax"]

        rename_map = {
            **display_cols,
            "gross_sales_ex_tax": "粗売上",
            "net_sales_ex_tax": "実売上",
            "discount_amount_ex_tax": "値引額",
            "gross_profit": "粗利額",
            sales_col: "売上",
        }
        st.dataframe(
            top[show_cols].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
        )

    with col_bottom:
        st.markdown("**Bottom 15**")
        if rank_metric == "売上":
            bottom = product_ranked.nsmallest(15, sales_col)
            show_cols_b = show_cols
        elif rank_metric == "粗利率":
            bottom = product_ranked.nsmallest(15, "粗利率(%)")
            show_cols_b = show_cols
        else:
            bottom = product_ranked.nsmallest(15, "値引率(%)")
            show_cols_b = show_cols

        st.dataframe(
            bottom[show_cols_b].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # --- Product Trend ---
    st.subheader("商品別トレンド")

    # Let user pick products to compare
    all_products = sorted(df_cat["cat_s"].unique().tolist())
    selected_products = st.multiselect(
        "比較する商品を選択 (小分類)",
        options=all_products,
        default=all_products[:3] if len(all_products) >= 3 else all_products,
        key="product_trend_select",
    )

    if selected_products:
        # Get full time-range data for selected products
        df_trend = df_cat[
            (df_cat["cat_s"].isin(selected_products))
            & (df_cat["store_id"].isin(filters["store_ids"]))
            & (df_cat["dept_id"].isin(filters["dept_ids"]))
        ]

        if not df_trend.empty:
            trend_agg = df_trend.groupby(["ym", "cat_s"]).agg({
                sales_col: "sum",
                "gross_profit": "sum",
                "net_sales_ex_tax": "sum",
            }).reset_index()

            trend_agg["粗利率(%)"] = (
                trend_agg["gross_profit"] / trend_agg["net_sales_ex_tax"] * 100
            ).round(1)

            col_t1, col_t2 = st.columns(2)

            with col_t1:
                fig_sales = chart_line_trend(
                    trend_agg,
                    x_col="ym",
                    y_col=sales_col,
                    color_col="cat_s",
                    title="売上推移",
                    y_title="金額 (฿)",
                )
                st.plotly_chart(fig_sales, use_container_width=True)

            with col_t2:
                fig_margin = chart_line_trend(
                    trend_agg,
                    x_col="ym",
                    y_col="粗利率(%)",
                    color_col="cat_s",
                    title="粗利率推移",
                    y_title="粗利率 (%)",
                )
                st.plotly_chart(fig_margin, use_container_width=True)

    st.divider()

    # --- Full Product Table ---
    st.subheader("商品一覧")

    full_display = product_ranked[[
        "dept_id", "cat_l", "cat_m", "cat_s",
        sales_col, "gross_profit", "粗利率(%)", "値引率(%)",
        "qty", "ランク", "売上累積比(%)",
    ]].rename(columns={
        "dept_id": "部門",
        "cat_l": "大分類",
        "cat_m": "中分類",
        "cat_s": "小分類",
        sales_col: "売上",
        "gross_profit": "粗利額",
        "qty": "数量",
    })

    st.dataframe(
        full_display,
        use_container_width=True,
        hide_index=True,
        height=500,
    )
