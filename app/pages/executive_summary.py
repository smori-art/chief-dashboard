"""
Executive Summary Page - 全社概況

Displays:
- AI summary report (top)
- KPI cards (sales, gross profit, discount, item unit price, etc.)
- Monthly trend (immediately below KPIs)
- Department composition (pie charts + compact table)
- Store composition (pie charts + compact table)
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS,
    NEGATIVE,
    POSITIVE,
    TEXT_SECONDARY,
    chart_line_trend,
    filter_dataframe,
    get_sales_column,
    render_kpi_card,
    render_sidebar_filters,
)
from app.data import load_forecast, load_sales_monthly, load_store_pl

APP_VERSION = "v1.2.0"


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


def _ym_to_display(ym: str) -> str:
    """Convert 'YYYY-MM' to 'YY/M' display format."""
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y % 100}/{m}"


def _pct(cur: float | None, ref: float | None) -> float | None:
    if cur is None or ref is None or ref == 0:
        return None
    return cur / ref * 100


def _agg_metrics(
    df: pd.DataFrame, ym: str, store_ids: list, dept_ids: list, sales_col: str,
) -> dict | None:
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
    qty = t["qty"]
    return {
        "sales": t[sales_col],
        "net_sales": net,
        "gross_profit": t["gross_profit"],
        "margin": (t["gross_profit"] / net * 100) if net else 0,
        "discount_rate": (t["discount_amount_ex_tax"] / gross * 100) if gross else 0,
        "refund": t["refund_amount"],
        "receipts": t["receipts"],
        "qty": qty,
        "basket": (net / t["receipts"]) if t["receipts"] else 0,
        "unit_price": (net / qty) if qty else 0,
    }


def _pie_chart(
    names: list[str], values: list[float], title: str,
) -> go.Figure:
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
    """Build a composition table: 1000THB units, integer percentages."""
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

    result = pd.DataFrame()
    result["名称"] = cur[group_name_col]
    # 1000THB unit, integer, with thousand separator as string
    sales_k = (cur[sales_col].values / 1000).round(0).astype(int)
    profit_k = (cur["gross_profit"].values / 1000).round(0).astype(int)
    result["売上(千฿)"] = [f"{v:,}" for v in sales_k]
    result["粗利(千฿)"] = [f"{v:,}" for v in profit_k]
    result["売上構成比"] = [f"{v}%" for v in (cur[sales_col].values / total_sales * 100).round(0).astype(int)]
    result["粗利構成比"] = [f"{v}%" for v in (cur["gross_profit"].values / total_profit * 100).round(0).astype(int)]

    # Raw values for AI summary and sorting
    result["_売上_raw"] = cur[sales_col].values
    result["_粗利_raw"] = cur["gross_profit"].values

    for period_label in ["前年", "前々年", "前月"]:
        ref = frames.get(period_label)
        if ref is not None:
            ref_map_sales = dict(zip(ref[group_name_col], ref[sales_col]))
            ref_map_profit = dict(zip(ref[group_name_col], ref["gross_profit"]))
            result[f"売上{period_label}比"] = result.apply(
                lambda r, rms=ref_map_sales: int(round(r["_売上_raw"] / rms[r["名称"]] * 100))
                if r["名称"] in rms and rms[r["名称"]] > 0 else None,
                axis=1,
            )
            result[f"粗利{period_label}比"] = result.apply(
                lambda r, rmp=ref_map_profit: int(round(r["_粗利_raw"] / rmp[r["名称"]] * 100))
                if r["名称"] in rmp and rmp[r["名称"]] > 0 else None,
                axis=1,
            )
        else:
            result[f"売上{period_label}比"] = None
            result[f"粗利{period_label}比"] = None

    result = result.sort_values("_売上_raw", ascending=False)
    return result


def _agg_pl(
    df_pl: pd.DataFrame, ym: str, store_ids: list,
) -> dict | None:
    """Aggregate store PL data to company level for a given period."""
    sub = df_pl[(df_pl["ym"] == ym) & (df_pl["store_id"].isin(store_ids))]
    if sub.empty:
        return None
    t = sub.agg({
        "net_sales": "sum",
        "cogs": "sum",
        "gross_profit": "sum",
        "personnel_expense": "sum",
        "rent_expense": "sum",
        "utility_expense": "sum",
        "depreciation_expense": "sum",
        "other_opex": "sum",
        "total_opex": "sum",
        "operating_profit": "sum",
    })
    ns = t["net_sales"]
    return {
        "net_sales": ns,
        "cogs": t["cogs"],
        "gross_profit": t["gross_profit"],
        "gross_margin_pct": (t["gross_profit"] / ns * 100) if ns else 0,
        "personnel_expense": t["personnel_expense"],
        "rent_expense": t["rent_expense"],
        "utility_expense": t["utility_expense"],
        "depreciation_expense": t["depreciation_expense"],
        "other_opex": t["other_opex"],
        "total_opex": t["total_opex"],
        "operating_profit": t["operating_profit"],
        "operating_margin_pct": (t["operating_profit"] / ns * 100) if ns else 0,
        "personnel_ratio_pct": (t["personnel_expense"] / ns * 100) if ns else 0,
        "rent_ratio_pct": (t["rent_expense"] / ns * 100) if ns else 0,
        "utility_ratio_pct": (t["utility_expense"] / ns * 100) if ns else 0,
        "depreciation_ratio_pct": (t["depreciation_expense"] / ns * 100) if ns else 0,
        "other_opex_ratio_pct": (t["other_opex"] / ns * 100) if ns else 0,
        "total_opex_ratio_pct": (t["total_opex"] / ns * 100) if ns else 0,
    }


def _format_pct_cell(val) -> str:
    """Format a percentage value with color: green >=100, red <100."""
    if val is None or pd.isna(val):
        return "--"
    v = int(val)
    color = POSITIVE if v >= 100 else NEGATIVE
    return f'<span style="color:{color};font-weight:600">{v}%</span>'


def _render_comp_html_table(df: pd.DataFrame, prefix: str) -> None:
    """Render a composition table as colored HTML."""
    amount_col = f"{prefix}(千฿)"
    share_col = f"{prefix}構成比"
    yoy_col = f"{prefix}前年比"
    yoy2_col = f"{prefix}前々年比"
    mom_col = f"{prefix}前月比"

    header = f"<tr><th>名称</th><th>{amount_col}</th><th>構成比</th>"
    header += "<th>前年比</th><th>前々年比</th><th>前月比</th></tr>"

    rows = []
    for _, r in df.iterrows():
        row = f"<td>{r['名称']}</td>"
        row += f"<td style='text-align:right'>{r.get(amount_col, '--')}</td>"
        row += f"<td style='text-align:right'>{r.get(share_col, '--')}</td>"
        row += f"<td style='text-align:right'>{_format_pct_cell(r.get(yoy_col))}</td>"
        row += f"<td style='text-align:right'>{_format_pct_cell(r.get(yoy2_col))}</td>"
        row += f"<td style='text-align:right'>{_format_pct_cell(r.get(mom_col))}</td>"
        rows.append(f"<tr>{row}</tr>")

    html = (
        '<div style="overflow-x:auto">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
        f"<thead style='background:#F1F5F9;color:#334155'>{header}</thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )
    # Add basic row borders via style
    html = html.replace("<tr>", '<tr style="border-bottom:1px solid #E2E8F0">')
    html = html.replace("<th>", '<th style="padding:6px 10px;text-align:left;font-weight:600">')
    html = html.replace("<td", '<td style="padding:5px 10px"')
    # Fix double style attrs
    html = re.sub(
        r'<td style="padding:5px 10px" style=\'text-align:right\'>',
        '<td style="padding:5px 10px;text-align:right">',
        html,
    )
    st.markdown(html, unsafe_allow_html=True)


def _display_comp_table(table: pd.DataFrame) -> None:
    """Display composition table in a compact two-tab layout (売上 / 粗利)."""
    if table.empty:
        return

    tab_sales, tab_profit = st.tabs(["売上", "粗利"])
    with tab_sales:
        _render_comp_html_table(table, "売上")
    with tab_profit:
        _render_comp_html_table(table, "粗利")


def _generate_ai_summary(
    agg_cur: dict, agg_yoy: dict | None, agg_yoy2: dict | None,
    agg_mom: dict | None,
    dept_table: pd.DataFrame, store_table: pd.DataFrame,
    sales_label: str, cur_ym: str,
) -> str:
    """Generate an extended text summary of the current period performance."""
    lines: list[str] = []

    # Header
    y, m = cur_ym.split("-")
    lines.append(f"### {y}年{int(m)}月 全社概況\n")

    # Overall sales
    sales = agg_cur["sales"]
    lines.append(f"当月の{sales_label}（税抜）は **฿{sales:,.0f}** となりました。")

    if agg_yoy:
        yoy_pct = sales / agg_yoy["sales"] * 100 if agg_yoy["sales"] else 0
        yoy_diff = sales - agg_yoy["sales"]
        direction = "増収" if yoy_pct >= 100 else "減収"
        lines.append(
            f"前年同月比では **{yoy_pct:.1f}%**（{direction}、差額 ฿{yoy_diff:+,.0f}）となっており、"
            f"{'堅調な成長を維持しています。' if yoy_pct >= 100 else '前年を下回る結果となりました。'}"
        )
    if agg_yoy2:
        yoy2_pct = sales / agg_yoy2["sales"] * 100 if agg_yoy2["sales"] else 0
        lines.append(
            f"前々年同月比では **{yoy2_pct:.1f}%** であり、"
            f"{'中長期的にも成長基調にあります。' if yoy2_pct >= 100 else '2年前の水準を回復できていない状況です。'}"
        )
    if agg_mom:
        mom_pct = sales / agg_mom["sales"] * 100 if agg_mom["sales"] else 0
        lines.append(
            f"前月比では **{mom_pct:.1f}%** "
            f"{'と前月から伸長しました。' if mom_pct >= 100 else 'と前月から減少しています。'}"
        )

    lines.append("")

    # Margin
    margin = agg_cur["margin"]
    lines.append(f"粗利率は **{margin:.1f}%** です。")
    if agg_yoy:
        margin_diff = margin - agg_yoy["margin"]
        direction = "改善" if margin_diff >= 0 else "悪化"
        lines.append(
            f"前年同月の粗利率 {agg_yoy['margin']:.1f}% と比較して "
            f"**{margin_diff:+.1f}pt** の{direction}となっています。"
        )

    # Discount
    disc = agg_cur["discount_rate"]
    lines.append(f"値引率は **{disc:.1f}%** です。")
    if agg_yoy:
        disc_diff = disc - agg_yoy["discount_rate"]
        if abs(disc_diff) >= 0.1:
            lines.append(
                f"前年比 {disc_diff:+.1f}pt であり、"
                f"{'値引コントロールが課題です。' if disc_diff > 0 else '値引の適正化が進んでいます。'}"
            )

    lines.append("")

    # Unit price & basket
    unit_price = agg_cur["unit_price"]
    basket = agg_cur["basket"]
    receipts = int(agg_cur["receipts"])
    lines.append(
        f"客単価は **฿{basket:,.0f}**、商品販売単価は **฿{unit_price:,.0f}**、"
        f"レシート件数は **{receipts:,}件** です。"
    )
    if agg_yoy:
        basket_pct = basket / agg_yoy["basket"] * 100 if agg_yoy["basket"] else 0
        up_pct = unit_price / agg_yoy["unit_price"] * 100 if agg_yoy["unit_price"] else 0
        rcpt_pct = receipts / agg_yoy["receipts"] * 100 if agg_yoy["receipts"] else 0
        lines.append(
            f"客単価は前年比 {basket_pct:.0f}%、"
            f"商品販売単価は前年比 {up_pct:.0f}%、"
            f"レシート件数は前年比 {rcpt_pct:.0f}% です。"
        )

    lines.append("")

    # Department highlights
    if not dept_table.empty and "売上前年比" in dept_table.columns:
        valid = dept_table.dropna(subset=["売上前年比"])
        if not valid.empty:
            best = valid.loc[valid["売上前年比"].idxmax()]
            worst = valid.loc[valid["売上前年比"].idxmin()]
            lines.append(
                f"**【部門別注目ポイント】** "
                f"前年比で最も好調なのは **{best['名称']}**（前年比 {int(best['売上前年比'])}%）で、"
                f"全社の成長を牽引しています。"
                f"一方、**{worst['名称']}**（前年比 {int(worst['売上前年比'])}%）は課題があり、"
                f"要因分析と対策立案が求められます。"
            )

    # Store highlights
    if not store_table.empty and "売上前年比" in store_table.columns:
        valid = store_table.dropna(subset=["売上前年比"])
        if not valid.empty:
            best = valid.loc[valid["売上前年比"].idxmax()]
            worst = valid.loc[valid["売上前年比"].idxmin()]
            lines.append(
                f"**【店舗別注目ポイント】** "
                f"**{best['名称']}**（前年比 {int(best['売上前年比'])}%）が最も伸長しており、"
                f"好事例として他店舗への横展開を検討すべきです。"
                f"**{worst['名称']}**（前年比 {int(worst['売上前年比'])}%）は低調であり、"
                f"改善施策の優先的な投入が望まれます。"
            )

    return "\n\n".join(lines)


# ── Main render ──────────────────────────────────────────────────────────

def render() -> None:
    """Render Executive Summary page."""

    # ── System header with version ───────────────────────────────────────
    hdr_left, hdr_right = st.columns([4, 1])
    with hdr_left:
        st.markdown(
            '<p style="font-size:1.1rem;font-weight:700;color:#475569;'
            'letter-spacing:0.06em;margin-bottom:0">'
            'LOPIA JAPAN Thailand 月次ダッシュボード</p>',
            unsafe_allow_html=True,
        )
    with hdr_right:
        st.markdown(
            f'<p style="text-align:right;font-size:0.72rem;color:#94A3B8;'
            f'margin-bottom:0">{APP_VERSION}</p>',
            unsafe_allow_html=True,
        )

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

    # Build composition tables early (needed for AI summary)
    dept_table = _build_comp_table(
        df, "dept_id", "dept_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
    )
    store_table = _build_comp_table(
        df, "store_id", "store_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
    )

    # =====================================================================
    # Section 0: AI Summary Report (top)
    # =====================================================================
    sales_label = "実売上" if filters["sales_type"] == "net" else "粗売上"
    summary = _generate_ai_summary(
        agg_cur, agg_yoy, agg_yoy2, agg_mom,
        dept_table, store_table, sales_label, cur_ym,
    )
    with st.expander("AI 概況レポート", expanded=True):
        st.markdown(summary)

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
            "refund", "receipts", "basket", "qty", "unit_price",
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
            sparks["unit_price"] = (_sp["net_sales_ex_tax"] / _sp["qty"]).round(0).tolist()

    # =====================================================================
    # Section 1: KPI Cards
    # =====================================================================
    st.divider()
    st.subheader(f"月次KPI ({cur_ym})")

    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        render_kpi_card(
            label="商品販売単価", value=agg_cur["unit_price"], prefix="฿", fmt=",.0f",
            comparisons=_comps("unit_price"), sparkline=sparks["unit_price"],
        )

    col6, col7, col8, col9 = st.columns(4)
    with col6:
        render_kpi_card(
            label="返品返金額", value=agg_cur["refund"], prefix="฿",
            comparisons=_comps("refund"), sparkline=sparks["refund"],
        )
    with col7:
        render_kpi_card(
            label="レシート件数", value=int(agg_cur["receipts"]),
            comparisons=_comps("receipts"), sparkline=sparks["receipts"],
        )
    with col8:
        render_kpi_card(
            label="客単価", value=agg_cur["basket"], prefix="฿", fmt=",.0f",
            comparisons=_comps("basket"), sparkline=sparks["basket"],
        )
    with col9:
        render_kpi_card(
            label="売上点数", value=int(agg_cur["qty"]),
            comparisons=_comps("qty"), sparkline=sparks["qty"],
        )

    # =====================================================================
    # Section 1.5: PL-based KPI Cards + Company P&L Table
    # =====================================================================
    df_pl = load_store_pl()
    if not df_pl.empty:
        pl_cur = _agg_pl(df_pl, cur_ym, filters["store_ids"])
        pl_yoy = _agg_pl(df_pl, _shift_ym(cur_ym, years=-1), filters["store_ids"])
        pl_yoy2 = _agg_pl(df_pl, _shift_ym(cur_ym, years=-2), filters["store_ids"])
        pl_mom = _agg_pl(df_pl, _shift_ym(cur_ym, months=-1), filters["store_ids"])
        pl_mom2 = _agg_pl(df_pl, _shift_ym(cur_ym, months=-2), filters["store_ids"])

        if pl_cur is not None:
            def _pl_comps(key: str) -> list[dict]:
                return [
                    {"label": "前年", "value": _pct(pl_cur[key], pl_yoy[key] if pl_yoy else None)},
                    {"label": "前々年", "value": _pct(pl_cur[key], pl_yoy2[key] if pl_yoy2 else None)},
                    {"label": "前月", "value": _pct(pl_cur[key], pl_mom[key] if pl_mom else None)},
                ]

            def _ratio_comps(key: str) -> list[dict]:
                """For ratio KPIs, show pt difference instead of percentage."""
                comps = []
                for lbl, ref in [("前年", pl_yoy), ("前々年", pl_yoy2), ("前月", pl_mom)]:
                    if ref is None:
                        comps.append({"label": lbl, "value": None})
                    else:
                        diff = pl_cur[key] - ref[key]
                        # Use 100+diff so positive diff shows as ▲, negative as ▼
                        comps.append({"label": lbl, "value": 100 + diff})
                return comps

            st.divider()
            st.subheader("PL指標")
            pc1, pc2, pc3, pc4, pc5 = st.columns(5)
            with pc1:
                render_kpi_card(
                    label="営業利益率", value=pl_cur["operating_margin_pct"],
                    suffix="%", fmt=".1f", comparisons=_ratio_comps("operating_margin_pct"),
                )
            with pc2:
                render_kpi_card(
                    label="人件費率", value=pl_cur["personnel_ratio_pct"],
                    suffix="%", fmt=".1f", comparisons=_ratio_comps("personnel_ratio_pct"),
                )
            with pc3:
                render_kpi_card(
                    label="販管費比率", value=pl_cur["total_opex_ratio_pct"],
                    suffix="%", fmt=".1f", comparisons=_ratio_comps("total_opex_ratio_pct"),
                )
            with pc4:
                render_kpi_card(
                    label="家賃比率", value=pl_cur["rent_ratio_pct"],
                    suffix="%", fmt=".1f", comparisons=_ratio_comps("rent_ratio_pct"),
                )
            with pc5:
                render_kpi_card(
                    label="減価償却費比率", value=pl_cur["depreciation_ratio_pct"],
                    suffix="%", fmt=".1f", comparisons=_ratio_comps("depreciation_ratio_pct"),
                )

            # ── Company-wide P&L Table ────────────────────────────────────
            st.divider()
            st.subheader("全社PL")

            pl_periods = [
                ("当期", pl_cur),
                ("前年", pl_yoy),
                ("前々年", pl_yoy2),
                ("前月", pl_mom),
                ("前々月", pl_mom2),
            ]

            pl_line_items = [
                ("売上高", "net_sales"),
                ("売上原価", "cogs"),
                ("粗利益", "gross_profit"),
                ("粗利率", "gross_margin_pct"),
                ("人件費", "personnel_expense"),
                ("家賃", "rent_expense"),
                ("水道光熱費", "utility_expense"),
                ("減価償却費", "depreciation_expense"),
                ("その他経費", "other_opex"),
                ("販管費合計", "total_opex"),
                ("営業利益", "operating_profit"),
                ("営業利益率", "operating_margin_pct"),
            ]

            ratio_keys = {"gross_margin_pct", "operating_margin_pct"}

            # Build header
            header_cols = ["科目", "当期"]
            for lbl, _ in pl_periods[1:]:
                header_cols.extend([lbl, f"{lbl}比"])
            header_html = "".join(
                f'<th style="padding:6px 10px;text-align:{"left" if i == 0 else "right"};'
                f'font-weight:600">{c}</th>'
                for i, c in enumerate(header_cols)
            )

            # Build rows
            rows_html = []
            for item_name, key in pl_line_items:
                is_ratio = key in ratio_keys
                is_subtotal = key in {"gross_profit", "total_opex", "operating_profit"}

                row_style = 'font-weight:600;background:#F8FAFC' if is_subtotal else ''
                cells = [f'<td style="padding:5px 10px;{row_style}">{item_name}</td>']

                cur_val = pl_cur[key] if pl_cur else None

                # Current period value
                if cur_val is not None:
                    if is_ratio:
                        cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">{cur_val:.1f}%</td>')
                    else:
                        cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">฿{cur_val:,.0f}</td>')
                else:
                    cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">--</td>')

                # Comparison periods
                for lbl, ref in pl_periods[1:]:
                    ref_val = ref[key] if ref else None
                    # Absolute value
                    if ref_val is not None:
                        if is_ratio:
                            cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">{ref_val:.1f}%</td>')
                        else:
                            cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">฿{ref_val:,.0f}</td>')
                    else:
                        cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">--</td>')

                    # Ratio comparison
                    if cur_val is not None and ref_val is not None:
                        if is_ratio:
                            diff = cur_val - ref_val
                            color = POSITIVE if diff >= 0 else NEGATIVE
                            cells.append(
                                f'<td style="padding:5px 10px;text-align:right;{row_style}">'
                                f'<span style="color:{color};font-weight:600">{diff:+.1f}pt</span></td>'
                            )
                        elif ref_val != 0:
                            pct = cur_val / ref_val * 100
                            color = POSITIVE if pct >= 100 else NEGATIVE
                            cells.append(
                                f'<td style="padding:5px 10px;text-align:right;{row_style}">'
                                f'<span style="color:{color};font-weight:600">{pct:.1f}%</span></td>'
                            )
                        else:
                            cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">--</td>')
                    else:
                        cells.append(f'<td style="padding:5px 10px;text-align:right;{row_style}">--</td>')

                rows_html.append(
                    f'<tr style="border-bottom:1px solid #E2E8F0">{"".join(cells)}</tr>'
                )

            pl_html = (
                '<div style="overflow-x:auto">'
                '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
                f'<thead style="background:#F1F5F9;color:#334155">'
                f'<tr style="border-bottom:1px solid #E2E8F0">{header_html}</tr></thead>'
                f'<tbody>{"".join(rows_html)}</tbody></table></div>'
            )
            st.markdown(pl_html, unsafe_allow_html=True)

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
        }).reset_index().sort_values("ym")
        trend_monthly["gross_margin_pct"] = (
            trend_monthly["gross_profit"] / trend_monthly["net_sales_ex_tax"] * 100
        ).round(1)
        # Convert ym to YY/M display format for x-axis
        trend_monthly["ym_disp"] = trend_monthly["ym"].apply(_ym_to_display)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            fig = chart_line_trend(
                trend_monthly, x_col="ym_disp", y_col=sales_col,
                title="月次売上推移", y_title="金額 (฿)",
            )
            fig.update_xaxes(type="category", tickmode="linear")
            st.plotly_chart(fig, use_container_width=True)
        with col_t2:
            fig = chart_line_trend(
                trend_monthly, x_col="ym_disp", y_col="gross_margin_pct",
                title="月次粗利率推移", y_title="粗利率 (%)",
            )
            fig.update_xaxes(type="category", tickmode="linear")
            st.plotly_chart(fig, use_container_width=True)

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

    _display_comp_table(dept_table)

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

    _display_comp_table(store_table)
