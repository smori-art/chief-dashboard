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
from app.data import load_budget_pl, load_forecast, load_sales_monthly, load_store_pl

# THB → JPY conversion rate
THB_TO_JPY = 4.2

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
    df_budget_pl: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a composition table: 1000THB units, integer percentages."""
    yms = {
        "当期": cur_ym,
        "予算": cur_ym,  # budget uses same ym
        "前年": _shift_ym(cur_ym, years=-1),
        "前々年": _shift_ym(cur_ym, years=-2),
        "前月": _shift_ym(cur_ym, months=-1),
        "前々月": _shift_ym(cur_ym, months=-2),
    }
    frames = {}
    for label, ym in yms.items():
        if label == "予算":
            continue  # handled separately below
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

    # Budget frame — aggregate from budget PL using store_name grouping
    if df_budget_pl is not None and not df_budget_pl.empty:
        bsub = df_budget_pl[
            (df_budget_pl["ym"] == cur_ym)
            & (df_budget_pl["store_id"].isin(store_ids))
        ]
        if not bsub.empty and group_name_col in bsub.columns:
            bagg = bsub.groupby(group_name_col).agg({"net_sales": "sum", "gross_profit": "sum"}).reset_index()
            # Rename net_sales to match sales_col for consistency
            bagg[sales_col] = bagg["net_sales"]
            frames["予算"] = bagg
        else:
            frames["予算"] = None
    else:
        frames["予算"] = None

    cur = frames["当期"]
    if cur is None:
        return pd.DataFrame()

    total_sales = cur[sales_col].sum()
    total_profit = cur["gross_profit"].sum()

    result = pd.DataFrame()
    result["名称"] = cur[group_name_col]
    sales_k = (cur[sales_col].values / 1000).round(0).astype(int)
    profit_k = (cur["gross_profit"].values / 1000).round(0).astype(int)
    result["売上(千฿)"] = [f"{v:,}" for v in sales_k]
    result["粗利(千฿)"] = [f"{v:,}" for v in profit_k]
    result["売上構成比"] = [f"{v}%" for v in (cur[sales_col].values / total_sales * 100).round(0).astype(int)]
    result["粗利構成比"] = [f"{v}%" for v in (cur["gross_profit"].values / total_profit * 100).round(0).astype(int)]

    result["_売上_raw"] = cur[sales_col].values
    result["_粗利_raw"] = cur["gross_profit"].values

    for period_label in ["予算", "前年", "前々年", "前月", "前々月"]:
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
    raw_col = f"_{prefix}_raw"
    comp_cols = [
        (f"{prefix}予算比", "予算比"),
        (f"{prefix}前年比", "前年比"),
        (f"{prefix}前々年比", "前々年比"),
        (f"{prefix}前月比", "前月比"),
        (f"{prefix}前々月比", "前々月比"),
    ]

    _th_l = '<th style="padding:6px 10px;text-align:left;font-weight:600">'
    _th_r = '<th style="padding:6px 10px;text-align:right;font-weight:600">'
    header = f"<tr>{_th_l}名称</th>{_th_r}{amount_col}</th>{_th_r}構成比</th>"
    for _, lbl in comp_cols:
        header += f"{_th_r}{lbl}</th>"
    header += "</tr>"

    _td_l = '<td style="padding:5px 10px">'
    _td_r = '<td style="padding:5px 10px;text-align:right">'

    rows = []
    for _, r in df.iterrows():
        row = f"{_td_l}{r['名称']}</td>"
        row += f"{_td_r}{r.get(amount_col, '--')}</td>"
        row += f"{_td_r}{r.get(share_col, '--')}</td>"
        for col_key, _ in comp_cols:
            row += f"{_td_r}{_format_pct_cell(r.get(col_key))}</td>"
        rows.append(f"<tr>{row}</tr>")

    # Totals row
    if raw_col in df.columns:
        total_raw = df[raw_col].sum()
        total_k = int(round(total_raw / 1000))
        total_row = (
            f'{_td_l}<b>合計</b></td>'
            f'{_td_r}<b>{total_k:,}</b></td>'
            f'{_td_r}<b>100%</b></td>'
        )
        for col_key, _ in comp_cols:
            vals = df[col_key].dropna()
            if not vals.empty:
                # Weighted average using raw values
                weights = df.loc[vals.index, raw_col]
                if weights.sum() > 0:
                    wavg = int(round((vals * weights).sum() / weights.sum()))
                    total_row += f"{_td_r}{_format_pct_cell(wavg)}</td>"
                else:
                    total_row += f"{_td_r}--</td>"
            else:
                total_row += f"{_td_r}--</td>"
        rows.append(
            f'<tr style="border-top:2px solid #CBD5E1;background:#F8FAFC">{total_row}</tr>'
        )

    html = (
        '<div style="overflow-x:auto">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
        f"<thead style='background:#F1F5F9;color:#334155'>{header}</thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )
    html = html.replace("<tr>", '<tr style="border-bottom:1px solid #E2E8F0">')
    st.markdown(html, unsafe_allow_html=True)


def _build_pl_comp_table(
    df_pl: pd.DataFrame,
    df_budget_pl: pd.DataFrame | None,
    group_name_col: str,
    cur_ym: str,
    store_ids: list,
    metric_key: str,
) -> pd.DataFrame:
    """Build a PL composition table for a given metric (e.g. operating_profit)."""
    yms = {
        "当期": cur_ym,
        "予算": cur_ym,
        "前年": _shift_ym(cur_ym, years=-1),
        "前々年": _shift_ym(cur_ym, years=-2),
        "前月": _shift_ym(cur_ym, months=-1),
        "前々月": _shift_ym(cur_ym, months=-2),
    }

    def _get_frame(src: pd.DataFrame, ym: str) -> pd.DataFrame | None:
        sub = src[(src["ym"] == ym) & (src["store_id"].isin(store_ids))]
        if sub.empty or group_name_col not in sub.columns:
            return None
        return sub.groupby(group_name_col).agg({metric_key: "sum", "net_sales": "sum"}).reset_index()

    frames = {}
    for label, ym in yms.items():
        if label == "予算":
            frames[label] = _get_frame(df_budget_pl, ym) if df_budget_pl is not None and not df_budget_pl.empty else None
        else:
            frames[label] = _get_frame(df_pl, ym)

    cur = frames["当期"]
    if cur is None:
        return pd.DataFrame()

    result = pd.DataFrame()
    result["名称"] = cur[group_name_col]
    val_k = (cur[metric_key].values / 1000).round(0).astype(int)
    result["金額(千฿)"] = [f"{v:,}" for v in val_k]
    # Ratio to sales
    result["対売上比"] = [f"{v:.1f}%" for v in (cur[metric_key].values / cur["net_sales"].values * 100)]
    result["_raw"] = cur[metric_key].values

    for period_label in ["予算", "前年", "前々年", "前月", "前々月"]:
        ref = frames.get(period_label)
        if ref is not None:
            ref_map = dict(zip(ref[group_name_col], ref[metric_key]))
            result[f"{period_label}比"] = result.apply(
                lambda r, rm=ref_map: int(round(r["_raw"] / rm[r["名称"]] * 100))
                if r["名称"] in rm and rm[r["名称"]] != 0 else None,
                axis=1,
            )
        else:
            result[f"{period_label}比"] = None

    result = result.sort_values("_raw", ascending=False)
    return result


def _render_pl_comp_html_table(df: pd.DataFrame) -> None:
    """Render a PL composition table as colored HTML."""
    comp_labels = ["予算比", "前年比", "前々年比", "前月比", "前々月比"]

    _th_l = '<th style="padding:6px 10px;text-align:left;font-weight:600">'
    _th_r = '<th style="padding:6px 10px;text-align:right;font-weight:600">'
    _td_l = '<td style="padding:5px 10px">'
    _td_r = '<td style="padding:5px 10px;text-align:right">'

    header = f"<tr>{_th_l}名称</th>{_th_r}金額(千฿)</th>{_th_r}対売上比</th>"
    for lbl in comp_labels:
        header += f"{_th_r}{lbl}</th>"
    header += "</tr>"

    rows = []
    for _, r in df.iterrows():
        row = f"{_td_l}{r['名称']}</td>"
        row += f"{_td_r}{r.get('金額(千฿)', '--')}</td>"
        row += f"{_td_r}{r.get('対売上比', '--')}</td>"
        for lbl in comp_labels:
            row += f"{_td_r}{_format_pct_cell(r.get(lbl))}</td>"
        rows.append(f"<tr>{row}</tr>")

    # Totals row
    if "_raw" in df.columns:
        total_raw = df["_raw"].sum()
        total_k = int(round(total_raw / 1000))
        total_row = (
            f'{_td_l}<b>合計</b></td>'
            f'{_td_r}<b>{total_k:,}</b></td>'
            f'{_td_r}--</td>'
        )
        for lbl in comp_labels:
            vals = df[lbl].dropna()
            if not vals.empty:
                weights = df.loc[vals.index, "_raw"].abs()
                if weights.sum() > 0:
                    wavg = int(round((vals * weights).sum() / weights.sum()))
                    total_row += f"{_td_r}{_format_pct_cell(wavg)}</td>"
                else:
                    total_row += f"{_td_r}--</td>"
            else:
                total_row += f"{_td_r}--</td>"
        rows.append(
            f'<tr style="border-top:2px solid #CBD5E1;background:#F8FAFC">{total_row}</tr>'
        )

    html = (
        '<div style="overflow-x:auto">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
        f"<thead style='background:#F1F5F9;color:#334155'>{header}</thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )
    html = html.replace("<tr>", '<tr style="border-bottom:1px solid #E2E8F0">')
    st.markdown(html, unsafe_allow_html=True)


def _display_comp_table(
    table: pd.DataFrame,
    df_pl: pd.DataFrame | None = None,
    df_budget_pl: pd.DataFrame | None = None,
    group_name_col: str = "store_name",
    cur_ym: str = "",
    store_ids: list | None = None,
) -> None:
    """Display composition table with sales/profit + PL item tabs."""
    if table.empty:
        return

    has_pl = df_pl is not None and store_ids
    if has_pl:
        tab_labels = ["売上", "粗利", "営業利益", "人件費", "販管費", "家賃", "減価償却費"]
    else:
        tab_labels = ["売上", "粗利"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_comp_html_table(table, "売上")
    with tabs[1]:
        _render_comp_html_table(table, "粗利")

    if has_pl:
        pl_tab_metrics = [
            ("operating_profit", 2),
            ("personnel_expense", 3),
            ("total_opex", 4),
            ("rent_expense", 5),
            ("depreciation_expense", 6),
        ]
        for metric_key, tab_idx in pl_tab_metrics:
            with tabs[tab_idx]:
                pl_table = _build_pl_comp_table(
                    df_pl, df_budget_pl, group_name_col, cur_ym, store_ids, metric_key,
                )
                if not pl_table.empty:
                    _render_pl_comp_html_table(pl_table)
                else:
                    st.info("データがありません")



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

    # Load PL data early (needed for composition tables)
    df_pl = load_store_pl()
    df_budget_pl = load_budget_pl()

    # Build composition tables
    dept_table = _build_comp_table(
        df, "dept_id", "dept_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
    )
    store_table = _build_comp_table(
        df, "store_id", "store_name", cur_ym,
        filters["store_ids"], filters["dept_ids"], sales_col,
        df_budget_pl=df_budget_pl,
    )

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
    if not df_pl.empty:
        pl_cur = _agg_pl(df_pl, cur_ym, filters["store_ids"])
        pl_yoy = _agg_pl(df_pl, _shift_ym(cur_ym, years=-1), filters["store_ids"])
        pl_yoy2 = _agg_pl(df_pl, _shift_ym(cur_ym, years=-2), filters["store_ids"])
        pl_mom = _agg_pl(df_pl, _shift_ym(cur_ym, months=-1), filters["store_ids"])
        pl_mom2 = _agg_pl(df_pl, _shift_ym(cur_ym, months=-2), filters["store_ids"])
        pl_budget = _agg_pl(df_budget_pl, cur_ym, filters["store_ids"]) if not df_budget_pl.empty else None

        if pl_cur is not None:
            # Cost ratio keys: lower is better (invert badge color)
            _cost_ratio_keys = {
                "personnel_ratio_pct", "rent_ratio_pct",
                "total_opex_ratio_pct", "depreciation_ratio_pct",
            }

            def _ratio_comps(key: str) -> list[dict]:
                """For ratio KPIs, show pt difference instead of percentage."""
                invert = key in _cost_ratio_keys
                comps = []
                for lbl, ref in [("前年", pl_yoy), ("前々年", pl_yoy2), ("前月", pl_mom), ("予算", pl_budget)]:
                    if ref is None:
                        comps.append({"label": lbl, "value": None})
                    else:
                        diff = pl_cur[key] - ref[key]
                        # For cost ratios, invert: negative diff = good (show as >=100)
                        badge_val = 100 - diff if invert else 100 + diff
                        comps.append({"label": lbl, "value": badge_val})
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
            st.caption(f"単位: 千THB / 千JPY（換算レート: 1 THB = {THB_TO_JPY} JPY）")

            pl_comparisons = [
                ("予算比", pl_budget),
                ("前年比", pl_yoy),
                ("前々年比", pl_yoy2),
                ("前月比", pl_mom),
                ("前々月比", pl_mom2),
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
            # Cost items: higher = worse (color inverted)
            cost_keys = {
                "cogs", "personnel_expense", "rent_expense", "utility_expense",
                "depreciation_expense", "other_opex", "total_opex",
            }

            # ── Header ──
            th = '<th style="padding:6px 8px;text-align:{a};font-weight:600;' \
                 'white-space:nowrap;border-bottom:2px solid #CBD5E1;font-size:0.72rem">{t}</th>'
            header_parts = [
                th.format(a="left", t="科目"),
                th.format(a="right", t="当期(千฿)"),
                th.format(a="right", t="当期(千¥)"),
            ]
            for lbl, _ in pl_comparisons:
                header_parts.append(th.format(a="right", t=lbl))
            header_html = "".join(header_parts)

            # ── Rows ──
            _td = '<td style="padding:4px 8px;text-align:{a};{s}">{v}</td>'
            rows_html = []
            for item_name, key in pl_line_items:
                is_ratio = key in ratio_keys
                is_sub = key in {"gross_profit", "total_opex", "operating_profit"}
                rs = "font-weight:600;background:#F8FAFC" if is_sub else ""

                cells = [_td.format(a="left", s=rs + ";white-space:nowrap", v=item_name)]
                cur_val = pl_cur[key]

                # Current: 千THB + 千JPY
                if is_ratio:
                    cells.append(_td.format(a="right", s=rs, v=f"{cur_val:.1f}%"))
                    cells.append(_td.format(a="right", s=rs, v="--"))
                else:
                    thb_k = cur_val / 1000
                    jpy_k = cur_val * THB_TO_JPY / 1000
                    cells.append(_td.format(a="right", s=rs, v=f"฿{thb_k:,.0f}"))
                    cells.append(_td.format(a="right", s=rs, v=f"¥{jpy_k:,.0f}"))

                # Comparison ratios only
                is_cost = key in cost_keys
                for lbl, ref in pl_comparisons:
                    ref_val = ref[key] if ref else None
                    if cur_val is not None and ref_val is not None:
                        if is_ratio:
                            diff = cur_val - ref_val
                            color = POSITIVE if diff >= 0 else NEGATIVE
                            cells.append(_td.format(
                                a="right", s=rs,
                                v=f'<span style="color:{color};font-weight:600">{diff:+.1f}pt</span>',
                            ))
                        elif ref_val != 0:
                            pct = cur_val / ref_val * 100
                            # Cost items: lower is better (invert color)
                            if is_cost:
                                color = POSITIVE if pct <= 100 else NEGATIVE
                            else:
                                color = POSITIVE if pct >= 100 else NEGATIVE
                            cells.append(_td.format(
                                a="right", s=rs,
                                v=f'<span style="color:{color};font-weight:600">{pct:.1f}%</span>',
                            ))
                        else:
                            cells.append(_td.format(a="right", s=rs, v="--"))
                    else:
                        cells.append(_td.format(a="right", s=rs, v="--"))

                rows_html.append(
                    f'<tr style="border-bottom:1px solid #E2E8F0">{"".join(cells)}</tr>'
                )

            pl_html = (
                '<div style="overflow-x:auto">'
                '<table style="width:100%;border-collapse:collapse;font-size:0.78rem">'
                f'<thead style="background:#F1F5F9;color:#334155">'
                f'<tr>{header_html}</tr></thead>'
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

    _display_comp_table(
        dept_table,
        df_pl=None,  # dept grouping not in store PL
        df_budget_pl=None,
        group_name_col="dept_name",
        cur_ym=cur_ym,
        store_ids=filters["store_ids"],
    )

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

    _display_comp_table(
        store_table,
        df_pl=df_pl,
        df_budget_pl=df_budget_pl,
        group_name_col="store_name",
        cur_ym=cur_ym,
        store_ids=filters["store_ids"],
    )
