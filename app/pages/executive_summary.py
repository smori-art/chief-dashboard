"""
Executive Summary Page - 全社概況

Displays:
- KPI cards (sales, gross profit, discount, etc.) with YoY/YoY2/MoM
- Monthly trend (immediately below KPIs)
- Department composition (pie charts + table with period comparisons)
- Store composition (pie charts + table with period comparisons)
- AI-generated summary report
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS,
    TEXT_SECONDARY,
    _CHART_LAYOUT,
    chart_line_trend,
    filter_dataframe,
    get_sales_column,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_forecast, load_sales_monthly


# ── Helpers ──────────────────────────────────────────────────────────────

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


def _agg_metrics(
    df: pd.DataFrame, ym: str, store_ids: list, dept_ids: list, sales_col: str,
) -> dict | None:
    """Aggregate key metrics for a specific year-month."""
    sub = df[
        (df["ym"] == ym)
        & (df["store_id"].isin(store_ids))
        & (df["dept_id"].isin(dept_ids))
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


def _pie_chart(
    names: list[str], values: list[float], title: str,
) -> go.Figure:
    """Create a pastel pie chart with integer % labels."""
    fig = go.Figure(go.Pie(
        labels=names,
        values=values,
        hole=0.45,
        textinfo="label+percent",
        texttemplate="%{label}<br>%{percent:.0%}",
        textposition="outside",
        marker=dict(colors=COLORS[: len(names)]),
        sort=False,
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT_SECONDARY)),
        showlegend=False,
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _build_comp_table(
    df_full: pd.DataFrame,
    group_col: str,
    group_name_col: str,
    cur_ym: str,
    store_ids: list,
    dept_ids: list,
    sales_col: str,
) -> pd.DataFrame:
    """Build a composition table with period-over-period comparisons."""
    yms = {
        "当期": cur_ym,
        "前年": _shift_ym(cur_ym, years=-1),
        "前々年": _shift_ym(cur_ym, years=-2),
        "前月": _shift_ym(cur_ym, months=-1),
    }
    frames = {}
    for label, ym in yms.items():
        sub = df_full[
            (df_full["ym"] == ym)
            & (df_full["store_id"].isin(store_ids))
            & (df_full["dept_id"].isin(dept_ids))
        ]
        if sub.empty:
            frames[label] = None
            continue
        agg = sub.groupby(group_name_col).agg({
            sales_col: "sum", "gross_profit": "sum",
        }).reset_index()
        frames[label] = agg

    cur = frames["当期"]
    if cur is None:
        return pd.DataFrame()

    total_sales = cur[sales_col].sum()
    total_profit = cur["gross_profit"].sum()
    result = cur.rename(columns={
        group_name_col: "名称",
        sales_col: "売上",
        "gross_profit": "粗利",
    }).copy()
    result["売上構成比(%)"] = (result["売上"] / total_sales * 100).round(0).astype(int)
    result["粗利構成比(%)"] = (result["粗利"] / total_profit * 100).round(0).astype(int)

    for period_label in ["前年", "前々年", "前月"]:
        ref = frames.get(period_label)
        if ref is not None:
            ref_map_sales = dict(zip(ref[group_name_col], ref[sales_col]))
            ref_map_profit = dict(zip(ref[group_name_col], ref["gross_profit"]))
            result[f"売上{period_label}比(%)"] = result.apply(
                lambda r: round(r["売上"] / ref_map_sales[r["名称"]] * 100, 1)
                if r["名称"] in ref_map_sales and ref_map_sales[r["名称"]] > 0 else None,
                axis=1,
            )
            result[f"粗利{period_label}比(%)"] = result.apply(
                lambda r: round(r["粗利"] / ref_map_profit[r["名称"]] * 100, 1)
                if r["名称"] in ref_map_profit and ref_map_profit[r["名称"]] > 0 else None,
                axis=1,
            )
        else:
            result[f"売上{period_label}比(%)"] = None
            result[f"粗利{period_label}比(%)"] = None

    return result.sort_values("売上", ascending=False)


def _generate_ai_summary(
    agg_cur: dict, agg_yoy: dict | None, agg_mom: dict | None,
    dept_table: pd.DataFrame, store_table: pd.DataFrame,
    sales_label: str,
) -> str:
    """Generate a text summary of the current period performance."""
    lines: list[str] = []

    # Overall sales
    sales = agg_cur["sales"]
    lines.append(f"**{sales_label}**は **฿{sales:,.0f}**。")

    if agg_yoy:
        yoy_pct = sales / agg_yoy["sales"] * 100 if agg_yoy["sales"] else 0
        direction = "増収" if yoy_pct >= 100 else "減収"
        lines.append(f"前年同月比 **{yoy_pct:.1f}%**（{direction}）。")
    if agg_mom:
        mom_pct = sales / agg_mom["sales"] * 100 if agg_mom["sales"] else 0
        direction = "上昇" if mom_pct >= 100 else "下降"
        lines.append(f"前月比 **{mom_pct:.1f}%**（{direction}）。")

    # Margin
    margin = agg_cur["margin"]
    lines.append(f"粗利率は **{margin:.1f}%**。")
    if agg_yoy:
        margin_diff = margin - agg_yoy["margin"]
        direction = "改善" if margin_diff >= 0 else "悪化"
        lines.append(f"前年比 **{margin_diff:+.1f}pt**（{direction}）。")

    # Discount
    disc = agg_cur["discount_rate"]
    lines.append(f"値引率 **{disc:.1f}%**。")

    # Department highlights
    if not dept_table.empty and "売上前年比(%)" in dept_table.columns:
        valid = dept_table.dropna(subset=["売上前年比(%)"])
        if not valid.empty:
            best = valid.loc[valid["売上前年比(%)"].idxmax()]
            worst = valid.loc[valid["売上前年比(%)"].idxmin()]
            lines.append(
                f"部門別では **{best['名称']}**（前年比{best['売上前年比(%)']:.1f}%）が好調、"
                f"**{worst['名称']}**（前年比{worst['売上前年比(%)']:.1f}%）が課題。"
            )

    # Store highlights
    if not store_table.empty and "売上前年比(%)" in store_table.columns:
        valid = store_table.dropna(subset=["売上前年比(%)"])
        if not valid.empty:
            best = valid.loc[valid["売上前年比(%)"].idxmax()]
            worst = valid.loc[valid["売上前年比(%)"].idxmin()]
            lines.append(
                f"店舗別では **{best['名称']}**（前年比{best['売上前年比(%)']:.1f}%）が牽引、"
                f"**{worst['名称']}**（前年比{worst['売上前年比(%)']:.1f}%）が低調。"
            )

    # Basket
    basket = agg_cur["basket"]
    lines.append(f"客単価 **฿{basket:,.0f}**、レシート数 **{int(agg_cur['receipts']):,}**件。")

    return " ".join(lines)


# ── Main render ──────────────────────────────────────────────────────────

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
    cur_ym = filters["ym"]

    # ── Period aggregates ────────────────────────────────────────────────
    args = (df, cur_ym, filters["store_ids"], filters["dept_ids"], sales_col)

    def _agg(ym: str) -> dict | None:
        return _agg_metrics(df, ym, filters["store_ids"], filters["dept_ids"], sales_col)

    agg_cur = _agg(cur_ym)
    agg_yoy = _agg(_shift_ym(cur_ym, years=-1))
    agg_yoy2 = _agg(_shift_ym(cur_ym, years=-2))
    agg_mom = _agg(_shift_ym(cur_ym, months=-1))

    if agg_cur is None:
        st.warning("選択された条件に該当するデータがありません。")
        return

    def _comps(key: str) -> list[dict]:
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

    # ── Sparklines ───────────────────────────────────────────────────────
    df_trend_all = df[
        (df["store_id"].isin(filters["store_ids"]))
        & (df["dept_id"].isin(filters["dept_ids"]))
    ]
    sparks: dict[str, list[float] | None] = {
        k: None for k in [
            "sales", "gross_profit", "margin", "discount_rate",
            "refund", "receipts", "basket", "qty",
        ]
    }
    if not df_trend_all.empty:
        _sp = df_trend_all.groupby("ym").agg({
            "gross_sales_ex_tax": "sum", "net_sales_ex_tax": "sum",
            "discount_amount_ex_tax": "sum", "gross_profit": "sum",
            "qty": "sum", "receipts": "sum", "refund_amount": "sum",
        }).sort_index().tail(6)
        if len(_sp) >= 2:
            sparks["sales"] = _sp[sales_col].tolist()
            sparks["gross_profit"] = _sp["gross_profit"].tolist()
            sparks["margin"] = (_sp["gross_profit"] / _sp["net_sales_ex_tax"] * 100).round(1).tolist()
            sparks["discount_rate"] = (_sp["discount_amount_ex_tax"] / _sp["gross_sales_ex_tax"] * 100).round(1).tolist()
            sparks["refund"] = _sp["refund_amount"].tolist()
            sparks["receipts"] = _sp["receipts"].tolist()
            sparks["basket"] = (_sp["net_sales_ex_tax"] / _sp["receipts"]).round(0).tolist()
            sparks["qty"] = _sp["qty"].tolist()

    # =====================================================================
    # Section 1: KPI Cards
    # =====================================================================
    st.subheader(f"月次KPI ({cur_ym})")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        slbl = "実売上" if filters["sales_type"] == "net" else "粗売上"
        render_kpi_card(
            label=f"{slbl} (税抜)", value=agg_cur["sales"], prefix="฿",
            comparisons=_comps("sales"), sparkline=sparks["sales"],
            target=forecast_total,
        )
    with col2:
        render_kpi_card(
            label="粗利額", value=agg_cur["gross_profit"], prefix="฿",
            comparisons=_comps("gross_profit"), sparkline=sparks["gross_profit"],
        )
    with col3:
        render_kpi_card(
            label="粗利率", value=agg_cur["margin"], suffix="%", fmt=".1f",
            comparisons=_comps("margin"), sparkline=sparks["margin"],
        )
    with col4:
        render_kpi_card(
            label="値引率", value=agg_cur["discount_rate"], suffix="%", fmt=".1f",
            comparisons=_comps("discount_rate"), sparkline=sparks["discount_rate"],
        )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card(
            label="返品返金額", value=agg_cur["refund"], prefix="฿",
            comparisons=_comps("refund"), sparkline=sparks["refund"],
        )
    with col6:
        render_kpi_card(
            label="レシート件数", value=int(agg_cur["receipts"]),
            comparisons=_comps("receipts"), sparkline=sparks["receipts"],
        )
    with col7:
        render_kpi_card(
            label="客単価", value=agg_cur["basket"], prefix="฿", fmt=",.0f",
            comparisons=_comps("basket"), sparkline=sparks["basket"],
        )
    with col8:
        render_kpi_card(
            label="売上点数", value=int(agg_cur["qty"]),
            comparisons=_comps("qty"), sparkline=sparks["qty"],
        )

    # =====================================================================
    # Section 2: Monthly Trend (immediately below KPIs)
    # =====================================================================
    st.divider()
    st.subheader("月次推移")

    df_trend = df[
        (df["store_id"].isin(filters["store_ids"]))
        & (df["dept_id"].isin(filters["dept_ids"]))
    ]
    if not df_trend.empty:
        trend_monthly = df_trend.groupby("ym").agg({
            "gross_sales_ex_tax": "sum", "net_sales_ex_tax": "sum",
            "gross_profit": "sum",
        }).reset_index()
        trend_monthly["gross_margin_pct"] = (
            trend_monthly["gross_profit"] / trend_monthly["net_sales_ex_tax"] * 100
        ).round(1)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.plotly_chart(chart_line_trend(
                trend_monthly, x_col="ym", y_col=sales_col,
                title="月次売上推移", y_title="金額 (฿)",
            ), use_container_width=True)
        with col_t2:
            st.plotly_chart(chart_line_trend(
                trend_monthly, x_col="ym", y_col="gross_margin_pct",
                title="月次粗利率推移", y_title="粗利率 (%)",
            ), use_container_width=True)

    # =====================================================================
    # Section 3: Department Composition
    # =====================================================================
    st.divider()
    st.subheader("部門別構成比")

    dept_agg = df_filtered.groupby("dept_name").agg({
        sales_col: "sum", "gross_profit": "sum",
    }).reset_index()

    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(_pie_chart(
            dept_agg["dept_name"].tolist(),
            dept_agg[sales_col].tolist(),
            "売上構成",
        ), use_container_width=True)
    with col_right:
        st.plotly_chart(_pie_chart(
            dept_agg["dept_name"].tolist(),
            dept_agg["gross_profit"].tolist(),
            "粗利構成",
        ), use_container_width=True)

    # Department comparison table
    dept_table = _build_comp_table(
        df, "dept_id", "dept_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
    )
    if not dept_table.empty:
        st.dataframe(dept_table, use_container_width=True, hide_index=True)

    # =====================================================================
    # Section 4: Store Composition
    # =====================================================================
    st.divider()
    st.subheader("店舗別構成比")

    store_agg = df_filtered.groupby("store_name").agg({
        sales_col: "sum", "gross_profit": "sum",
    }).reset_index()

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.plotly_chart(_pie_chart(
            store_agg["store_name"].tolist(),
            store_agg[sales_col].tolist(),
            "売上構成",
        ), use_container_width=True)
    with col_s2:
        st.plotly_chart(_pie_chart(
            store_agg["store_name"].tolist(),
            store_agg["gross_profit"].tolist(),
            "粗利構成",
        ), use_container_width=True)

    # Store comparison table
    store_table = _build_comp_table(
        df, "store_id", "store_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
    )
    if not store_table.empty:
        st.dataframe(store_table, use_container_width=True, hide_index=True)

    # =====================================================================
    # Section 5: AI Summary Report
    # =====================================================================
    st.divider()
    st.subheader("AI 概況レポート")

    sales_label = "実売上" if filters["sales_type"] == "net" else "粗売上"
    summary = _generate_ai_summary(
        agg_cur, agg_yoy, agg_mom, dept_table, store_table, sales_label,
    )
    st.info(summary)
