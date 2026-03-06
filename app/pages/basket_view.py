"""
Basket Analysis Page - バスケット分析 (併買分析)

Displays:
- Co-purchase pair rankings
- Basket size distribution
- Cross-department purchase patterns
"""

from __future__ import annotations

from itertools import combinations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS_GRAY,
    _CHART_LAYOUT,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_basket_data


def render() -> None:
    """Render Basket Analysis page."""
    st.title("Basket Analysis - 併買分析")

    filters = render_sidebar_filters()
    df = load_basket_data()

    if filters.get("store_ids"):
        df = df[df["store_id"].isin(filters["store_ids"])]

    if df.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- KPI Summary ---
    st.subheader("バスケット概況")

    n_receipts = df["receipt_id"].nunique()
    total_sales = df["net_sales"].sum()
    avg_basket = total_sales / n_receipts if n_receipts else 0
    avg_items = df.groupby("receipt_id")["product_name"].count().mean()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("レシート数", n_receipts, fmt=",d")
    with col2:
        render_kpi_card("客単価", avg_basket, prefix="฿", fmt=",.0f")
    with col3:
        render_kpi_card("平均点数", avg_items, fmt=".1f")
    with col4:
        render_kpi_card("売上合計", total_sales, prefix="฿")

    st.divider()

    # --- Basket Size Distribution ---
    st.subheader("バスケットサイズ分布")

    basket_sizes = df.groupby("receipt_id")["product_name"].count().reset_index()
    basket_sizes.columns = ["receipt_id", "item_count"]
    size_dist = basket_sizes["item_count"].value_counts().sort_index().reset_index()
    size_dist.columns = ["点数", "レシート数"]

    fig_size = go.Figure(go.Bar(
        x=size_dist["点数"], y=size_dist["レシート数"],
        marker_color="#666",
    ))
    fig_size.update_layout(
        title="バスケットサイズ分布",
        xaxis_title="購入点数", yaxis_title="レシート数",
        height=350, **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_size, use_container_width=True)

    st.divider()

    # --- Co-Purchase Pairs ---
    st.subheader("併買ペアランキング")
    st.caption("同一レシート内で一緒に購入された商品ペアの頻度")

    # Build co-purchase pairs (sample for performance)
    receipt_groups = df.groupby("receipt_id")["product_name"].apply(list)
    pair_counts: dict[tuple[str, str], int] = {}
    for items in receipt_groups:
        unique_items = sorted(set(items))
        if len(unique_items) < 2:
            continue
        for a, b in combinations(unique_items, 2):
            pair = (a, b)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    if pair_counts:
        pairs_df = pd.DataFrame([
            {"商品A": a, "商品B": b, "併買回数": c, "併買率(%)": round(c / n_receipts * 100, 2)}
            for (a, b), c in pair_counts.items()
        ]).sort_values("併買回数", ascending=False)

        col_pair1, col_pair2 = st.columns([2, 1])
        with col_pair1:
            top_n = min(20, len(pairs_df))
            top_pairs = pairs_df.head(top_n)
            fig_pairs = go.Figure(go.Bar(
                x=top_pairs["併買回数"],
                y=top_pairs["商品A"] + " + " + top_pairs["商品B"],
                orientation="h",
                marker_color="#555",
            ))
            fig_pairs.update_layout(
                title=f"併買ペア Top{top_n}",
                height=max(350, top_n * 28),
                yaxis=dict(autorange="reversed"),
                **_CHART_LAYOUT,
            )
            st.plotly_chart(fig_pairs, use_container_width=True)

        with col_pair2:
            st.dataframe(
                pairs_df.head(30),
                use_container_width=True,
                hide_index=True,
                height=500,
            )

    st.divider()

    # --- Cross-Department Pattern ---
    st.subheader("部門間併買パターン")

    receipt_depts = df.groupby("receipt_id")["dept_id"].apply(lambda x: sorted(set(x)))
    dept_pair_counts: dict[tuple[str, str], int] = {}
    for depts in receipt_depts:
        if len(depts) < 2:
            continue
        for a, b in combinations(depts, 2):
            dept_pair_counts[(a, b)] = dept_pair_counts.get((a, b), 0) + 1

    if dept_pair_counts:
        dept_pairs_df = pd.DataFrame([
            {"部門A": a, "部門B": b, "併買回数": c}
            for (a, b), c in dept_pair_counts.items()
        ]).sort_values("併買回数", ascending=False)

        st.dataframe(dept_pairs_df, use_container_width=True, hide_index=True)
