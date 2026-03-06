"""
Alert Dashboard Page - アラート/異常検知

Displays:
- KPI threshold-based alerts
- Margin deterioration alerts
- OOS spike alerts
- Discount rate anomaly alerts
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    filter_dataframe,
    get_sales_column,
    render_sidebar_filters,
)
from app.data import load_oos_data, load_sales_monthly


def _severity_badge(level: str) -> str:
    colors = {"HIGH": "#c0392b", "MEDIUM": "#e67e22", "LOW": "#7f8c8d"}
    color = colors.get(level, "#999")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:0.8rem;font-weight:600">{level}</span>'


def render() -> None:
    """Render Alert Dashboard page."""
    st.title("アラート")

    filters = render_sidebar_filters()
    sales_col = get_sales_column(filters)

    df_sales = load_sales_monthly()
    df_sales_f = filter_dataframe(df_sales, filters)
    df_oos = load_oos_data()

    if df_sales_f.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    alerts: list[dict] = []

    # --- Margin Deterioration Alerts ---
    cross = df_sales_f.groupby(["store_name", "dept_name"]).agg({
        "gross_margin_pct": "mean",
        "gross_margin_yoy_diff": "mean",
        "net_sales_ex_tax": "sum",
        "gross_profit": "sum",
        "discount_rate_pct": "mean",
    }).reset_index()

    # Margin drop > 2pt
    margin_alerts = cross[cross["gross_margin_yoy_diff"] < -2]
    for _, row in margin_alerts.iterrows():
        severity = "HIGH" if row["gross_margin_yoy_diff"] < -5 else "MEDIUM"
        alerts.append({
            "severity": severity,
            "category": "粗利率悪化",
            "location": f"{row['store_name']} / {row['dept_name']}",
            "detail": f"粗利率 {row['gross_margin_pct']:.1f}% (前年差 {row['gross_margin_yoy_diff']:+.1f}pt)",
            "impact": f"粗利額 ฿{row['gross_profit']:,.0f}",
        })

    # High discount rate > 6%
    discount_alerts = cross[cross["discount_rate_pct"] > 6]
    for _, row in discount_alerts.iterrows():
        severity = "HIGH" if row["discount_rate_pct"] > 8 else "MEDIUM"
        alerts.append({
            "severity": severity,
            "category": "高値引率",
            "location": f"{row['store_name']} / {row['dept_name']}",
            "detail": f"値引率 {row['discount_rate_pct']:.1f}%",
            "impact": f"売上 ฿{row['net_sales_ex_tax']:,.0f}",
        })

    # Low margin < 15%
    low_margin = cross[cross["gross_margin_pct"] < 15]
    for _, row in low_margin.iterrows():
        alerts.append({
            "severity": "MEDIUM" if row["gross_margin_pct"] < 10 else "LOW",
            "category": "低粗利率",
            "location": f"{row['store_name']} / {row['dept_name']}",
            "detail": f"粗利率 {row['gross_margin_pct']:.1f}%",
            "impact": f"粗利額 ฿{row['gross_profit']:,.0f}",
        })

    # --- OOS Alerts ---
    if not df_oos.empty:
        if filters.get("store_ids"):
            df_oos_f = df_oos[df_oos["store_id"].isin(filters["store_ids"])]
        else:
            df_oos_f = df_oos

        oos_by_store = df_oos_f.groupby("store_id").agg(
            oos_count=("is_oos_suspect", "sum"),
            total=("is_oos_suspect", "count"),
            loss=("opportunity_loss_amount", "sum"),
        ).reset_index()
        oos_by_store["oos_rate"] = (oos_by_store["oos_count"] / oos_by_store["total"] * 100).round(1)

        high_oos = oos_by_store[oos_by_store["oos_rate"] > 12]
        for _, row in high_oos.iterrows():
            alerts.append({
                "severity": "HIGH" if row["oos_rate"] > 15 else "MEDIUM",
                "category": "欠品率上昇",
                "location": f"店舗 {row['store_id']}",
                "detail": f"欠品率 {row['oos_rate']:.1f}% ({int(row['oos_count'])}件)",
                "impact": f"機会損失 ฿{row['loss']:,.0f}",
            })

    # --- Display Alerts ---
    st.subheader("アラート一覧")

    # Summary counts
    high_count = sum(1 for a in alerts if a["severity"] == "HIGH")
    med_count = sum(1 for a in alerts if a["severity"] == "MEDIUM")
    low_count = sum(1 for a in alerts if a["severity"] == "LOW")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総アラート数", len(alerts))
    with col2:
        st.metric("HIGH", high_count)
    with col3:
        st.metric("MEDIUM", med_count)
    with col4:
        st.metric("LOW", low_count)

    st.divider()

    if not alerts:
        st.success("現在、閾値を超えるアラートはありません。")
        return

    # Filter by severity
    show_severity = st.multiselect(
        "表示する重要度",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"],
        key="alert_severity",
    )

    filtered_alerts = [a for a in alerts if a["severity"] in show_severity]
    filtered_alerts.sort(key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["severity"]])

    # Render alerts
    for alert in filtered_alerts:
        badge = _severity_badge(alert["severity"])
        st.markdown(
            f"{badge} **{alert['category']}** | {alert['location']}<br>"
            f"<span style='color:#555'>{alert['detail']} / {alert['impact']}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

    st.divider()

    # --- Alert Table ---
    st.subheader("アラート詳細テーブル")

    alert_df = pd.DataFrame(filtered_alerts)
    if not alert_df.empty:
        alert_df = alert_df.rename(columns={
            "severity": "重要度",
            "category": "カテゴリ",
            "location": "対象",
            "detail": "詳細",
            "impact": "影響",
        })
        st.dataframe(alert_df, use_container_width=True, hide_index=True)
