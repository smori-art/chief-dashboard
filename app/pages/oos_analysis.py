"""
OOS (Out-of-Stock) Analysis Page - 欠品分析

Displays:
- OOS rate summary (receipt-based vs inventory-based)
- Suspected OOS SKU list
- DOW × Timeband heatmap
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    chart_heatmap,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_oos_data


def render() -> None:
    """Render OOS Analysis page."""
    st.title("🚫 OOS Analysis - 欠品分析")

    filters = render_sidebar_filters()
    df = load_oos_data()

    if df.empty:
        st.warning("欠品分析データがありません。")
        return

    # Filter by stores and departments
    df_filtered = df.copy()
    if filters.get("store_ids"):
        df_filtered = df_filtered[df_filtered["store_id"].isin(filters["store_ids"])]
    if filters.get("dept_ids"):
        df_filtered = df_filtered[df_filtered["dept_id"].isin(filters["dept_ids"])]

    if df_filtered.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    # --- OOS Summary ---
    st.subheader("📊 欠品率サマリ")

    total_skus = df_filtered.groupby(["date", "store_id"])["sku"].nunique().mean()
    oos_skus = df_filtered[df_filtered["is_oos_suspect"]].groupby(["date", "store_id"])["sku"].nunique().mean()
    oos_rate = (oos_skus / total_skus * 100) if total_skus > 0 else 0
    total_loss = df_filtered[df_filtered["is_oos_suspect"]]["opportunity_loss_amount"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card(
            label="欠品率 (レシート推定)",
            value=oos_rate,
            suffix="%",
            fmt=".1f",
        )
    with col2:
        render_kpi_card(
            label="欠品疑いSKU数/日",
            value=int(oos_skus),
        )
    with col3:
        render_kpi_card(
            label="機会損失額 (推定)",
            value=total_loss,
            prefix="฿",
            fmt=",.0f",
        )
    with col4:
        st.metric(
            label="在庫ベース欠品率",
            value="データ未連携",
        )
        st.caption("在庫・発注データ連携後に表示")

    st.divider()

    # --- OOS by Department ---
    st.subheader("🏢 部門別欠品率")

    dept_oos = df_filtered.groupby("dept_id").agg(
        total_records=("sku", "count"),
        oos_records=("is_oos_suspect", "sum"),
        total_loss=("opportunity_loss_amount", "sum"),
    ).reset_index()

    dept_oos["欠品率(%)"] = (dept_oos["oos_records"] / dept_oos["total_records"] * 100).round(1)
    dept_oos = dept_oos.sort_values("欠品率(%)", ascending=False)

    dept_display = dept_oos.rename(columns={
        "dept_id": "部門",
        "total_records": "対象レコード数",
        "oos_records": "欠品疑い件数",
        "total_loss": "機会損失額",
    })
    st.dataframe(dept_display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Suspected OOS SKU List ---
    st.subheader("📋 欠品疑いSKUリスト")

    oos_skus_df = df_filtered[df_filtered["is_oos_suspect"]].copy()

    if oos_skus_df.empty:
        st.success("現在、欠品疑いのSKUはありません。")
    else:
        # Aggregate by SKU
        sku_agg = oos_skus_df.groupby(["sku", "dept_id", "product_name"]).agg(
            oos_days=("date", "nunique"),
            avg_expected_qty=("expected_qty", "mean"),
            avg_actual_qty=("actual_qty", "mean"),
            total_loss=("opportunity_loss_amount", "sum"),
        ).reset_index()

        sku_agg = sku_agg.sort_values("total_loss", ascending=False)

        display_skus = sku_agg.head(50).rename(columns={
            "sku": "商品コード",
            "dept_id": "部門",
            "product_name": "商品名",
            "oos_days": "欠品日数",
            "avg_expected_qty": "期待数量(平均)",
            "avg_actual_qty": "実績数量(平均)",
            "total_loss": "機会損失額",
        })

        st.dataframe(display_skus, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # --- DOW × Store Heatmap ---
    st.subheader("📅 曜日別欠品パターン")

    dow_names = {1: "月", 2: "火", 3: "水", 4: "木", 5: "金", 6: "土", 7: "日"}

    oos_heatmap = df_filtered.groupby(["dow", "store_id"]).agg(
        total=("sku", "count"),
        oos=("is_oos_suspect", "sum"),
    ).reset_index()

    oos_heatmap["欠品率(%)"] = (oos_heatmap["oos"] / oos_heatmap["total"] * 100).round(1)
    oos_heatmap["曜日"] = oos_heatmap["dow"].map(dow_names)

    if not oos_heatmap.empty:
        fig = chart_heatmap(
            oos_heatmap,
            x_col="store_id",
            y_col="曜日",
            value_col="欠品率(%)",
            title="曜日 × 店舗 欠品率ヒートマップ",
            color_scale="YlOrRd",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Comparison note ---
    st.subheader("📊 レシート推定 vs 在庫データ 比較")
    st.info(
        "現在はレシート推定による欠品率のみ表示しています。\n\n"
        "在庫・発注データが連携されると、以下の比較分析が可能になります：\n"
        "- レシート推定欠品率 vs 在庫ベース欠品率\n"
        "- 乖離分析（推定と実データの差異）\n"
        "- 発注タイミングの最適化提案"
    )
