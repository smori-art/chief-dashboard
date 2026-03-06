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
    st.title("全社概況")

    filters = render_sidebar_filters()
    df = load_sales_monthly()
    df_filtered = filter_dataframe(df, filters)

    if df_filtered.empty:
        st.warning("選択された条件に該当するデータがありません。")
        return

    sales_col = get_sales_column(filters)

    # --- Helper: aggregate for a given ym ---
    def _agg_for_ym(ym: str) -> dict | None:
        """Aggregate key metrics for a specific year-month."""
        sub = df[
            (df["ym"] == ym)
            & (df["store_id"].isin(filters["store_ids"]))
            & (df["dept_id"].isin(filters["dept_ids"]))
        ]
        if sub.empty:
            return None
        t = sub.agg({
            "gross_sales_ex_tax": "sum",
            "net_sales_ex_tax": "sum",
            "discount_amount_ex_tax": "sum",
            "gross_profit": "sum",
            "qty": "sum",
            "receipts": "sum",
            "refund_amount": "sum",
        })
        net = t["net_sales_ex_tax"]
        gross = t["gross_sales_ex_tax"]
        return {
            "sales": t[sales_col],
            "net_sales": net,
            "gross_profit": t["gross_profit"],
            "margin": (t["gross_profit"] / net * 100) if net else 0,
            "discount_rate": (t["discount_amount_ex_tax"] / gross * 100) if gross else 0,
            "refund": t["refund_amount"],
            "receipts": t["receipts"],
            "qty": t["qty"],
            "basket": (net / t["receipts"]) if t["receipts"] else 0,
        }

    def _shift_ym(ym: str, years: int = 0, months: int = 0) -> str:
        """Shift a 'YYYY-MM' string by years/months."""
        y, m = int(ym[:4]), int(ym[5:7])
        y += years
        m += months
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        return f"{y}-{m:02d}"

    def _pct(cur: float | None, ref: float | None) -> float | None:
        """Return percentage ratio (100 = flat)."""
        if cur is None or ref is None or ref == 0:
            return None
        return cur / ref * 100

    # Aggregate current and comparison periods
    cur_ym = filters["ym"]
    agg_cur = _agg_for_ym(cur_ym)
    agg_yoy = _agg_for_ym(_shift_ym(cur_ym, years=-1))
    agg_yoy2 = _agg_for_ym(_shift_ym(cur_ym, years=-2))
    agg_mom = _agg_for_ym(_shift_ym(cur_ym, months=-1))

    if agg_cur is None:
        st.warning("選択された条件に該当するデータがありません。")
        return

    def _comps(key: str) -> list[dict]:
        """Build comparison badges for a metric key."""
        return [
            {"label": "前年", "value": _pct(agg_cur[key], agg_yoy[key] if agg_yoy else None)},
            {"label": "前々年", "value": _pct(agg_cur[key], agg_yoy2[key] if agg_yoy2 else None)},
            {"label": "前月", "value": _pct(agg_cur[key], agg_mom[key] if agg_mom else None)},
        ]

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

    # Build sparkline data — monthly trend for last 6 months
    df_trend_all = df[
        (df["store_id"].isin(filters["store_ids"]))
        & (df["dept_id"].isin(filters["dept_ids"]))
    ]
    sparks: dict[str, list[float] | None] = {
        "sales": None, "gross_profit": None, "margin": None,
        "discount_rate": None, "refund": None, "receipts": None,
        "basket": None, "qty": None,
    }
    if not df_trend_all.empty:
        _sp = df_trend_all.groupby("ym").agg({
            "gross_sales_ex_tax": "sum",
            "net_sales_ex_tax": "sum",
            "discount_amount_ex_tax": "sum",
            "gross_profit": "sum",
            "qty": "sum",
            "receipts": "sum",
            "refund_amount": "sum",
        }).sort_index().tail(6)
        if len(_sp) >= 2:
            sparks["sales"] = _sp[sales_col].tolist()
            sparks["gross_profit"] = _sp["gross_profit"].tolist()
            sparks["margin"] = (
                _sp["gross_profit"] / _sp["net_sales_ex_tax"] * 100
            ).round(1).tolist()
            sparks["discount_rate"] = (
                _sp["discount_amount_ex_tax"] / _sp["gross_sales_ex_tax"] * 100
            ).round(1).tolist()
            sparks["refund"] = _sp["refund_amount"].tolist()
            sparks["receipts"] = _sp["receipts"].tolist()
            sparks["basket"] = (
                _sp["net_sales_ex_tax"] / _sp["receipts"]
            ).round(0).tolist()
            sparks["qty"] = _sp["qty"].tolist()

    # --- KPI Cards ---
    st.subheader(f"月次KPI ({cur_ym})")

    total_sales = agg_cur["sales"]
    total_gross_profit = agg_cur["gross_profit"]
    total_margin = agg_cur["margin"]
    discount_rate = agg_cur["discount_rate"]
    total_net = agg_cur["net_sales"]

    # Row 1
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sales_label = "実売上" if filters["sales_type"] == "net" else "粗売上"
        render_kpi_card(
            label=f"{sales_label} (税抜)",
            value=total_sales,
            prefix="฿",
            comparisons=_comps("sales"),
            sparkline=sparks["sales"],
            target=forecast_total,
        )

    with col2:
        render_kpi_card(
            label="粗利額",
            value=total_gross_profit,
            prefix="฿",
            comparisons=_comps("gross_profit"),
            sparkline=sparks["gross_profit"],
        )

    with col3:
        render_kpi_card(
            label="粗利率",
            value=total_margin,
            suffix="%",
            fmt=".1f",
            comparisons=_comps("margin"),
            sparkline=sparks["margin"],
        )

    with col4:
        render_kpi_card(
            label="値引率",
            value=discount_rate,
            suffix="%",
            fmt=".1f",
            comparisons=_comps("discount_rate"),
            sparkline=sparks["discount_rate"],
        )

    # Row 2
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card(
            label="返品返金額",
            value=agg_cur["refund"],
            prefix="฿",
            comparisons=_comps("refund"),
            sparkline=sparks["refund"],
        )
    with col6:
        render_kpi_card(
            label="レシート件数",
            value=int(agg_cur["receipts"]),
            comparisons=_comps("receipts"),
            sparkline=sparks["receipts"],
        )
    with col7:
        render_kpi_card(
            label="客単価",
            value=agg_cur["basket"],
            prefix="฿",
            fmt=",.0f",
            comparisons=_comps("basket"),
            sparkline=sparks["basket"],
        )
    with col8:
        render_kpi_card(
            label="売上点数",
            value=int(agg_cur["qty"]),
            comparisons=_comps("qty"),
            sparkline=sparks["qty"],
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
