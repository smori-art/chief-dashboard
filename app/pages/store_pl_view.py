"""
Store P&L Page — 店舗別損益計算書

Displays:
- P&L summary table (all stores side-by-side)
- Expense ratio breakdown (stacked bar)
- Operating margin trend
- YoY comparison
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    COLORS,
    NEGATIVE,
    POSITIVE,
    TEXT_SECONDARY,
    _CHART_LAYOUT,
    render_kpi_card,
)
from app.data import load_store_pl


APP_VERSION = "v1.2.0"

_PL_ROWS = [
    ("売上高", "net_sales"),
    ("売上原価", "cogs"),
    ("粗利益", "gross_profit"),
    ("  粗利率(%)", "gross_margin_pct"),
    ("人件費", "personnel_expense"),
    ("家賃", "rent_expense"),
    ("水道光熱費", "utility_expense"),
    ("減価償却費", "depreciation_expense"),
    ("その他経費", "other_opex"),
    ("販管費合計", "total_opex"),
    ("営業利益", "operating_profit"),
    ("  営業利益率(%)", "operating_margin_pct"),
]

_EXPENSE_ITEMS = [
    ("人件費", "personnel_expense", COLORS[0]),
    ("家賃", "rent_expense", COLORS[1]),
    ("水道光熱費", "utility_expense", COLORS[2]),
    ("減価償却費", "depreciation_expense", COLORS[3]),
    ("その他経費", "other_opex", COLORS[4]),
]


def _shift_ym(ym: str, years: int = 0, months: int = 0) -> str:
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
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y % 100}/{m}"


def _fmt_amount(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "--"
    return f"{int(round(v / 1000)):,}"


def _fmt_pct(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "--"
    return f"{v:.1f}%"


def _color_cell(val: float | None, is_pct_row: bool = False) -> str:
    """Color negative values red, positive green for profit rows."""
    if val is None or pd.isna(val):
        return "--"
    if is_pct_row:
        text = f"{val:.1f}%"
    else:
        text = f"{int(round(val / 1000)):,}"
    color = POSITIVE if val >= 0 else NEGATIVE
    return f'<span style="color:{color};font-weight:600">{text}</span>'


def render() -> None:
    """Render Store P&L page."""

    # Header
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

    st.title("店舗別PL (損益計算書)")

    df = load_store_pl()
    if df.empty:
        st.warning("PLデータがありません。")
        return

    # Sidebar: period selection
    with st.sidebar:
        ym_list = sorted(df["ym"].unique().tolist(), reverse=True)
        selected_ym = st.selectbox("期間", options=ym_list, index=0, key="pl_ym")

    cur = df[df["ym"] == selected_ym].copy()
    prev_ym = _shift_ym(selected_ym, years=-1)
    prev = df[df["ym"] == prev_ym].copy()

    if cur.empty:
        st.warning("選択された期間のデータがありません。")
        return

    stores = cur.sort_values("net_sales", ascending=False)["store_id"].tolist()
    store_names = dict(zip(cur["store_id"], cur["store_name"]))

    # =====================================================================
    # KPI Cards — Company total
    # =====================================================================
    total_sales = cur["net_sales"].sum()
    total_gp = cur["gross_profit"].sum()
    total_op = cur["operating_profit"].sum()
    total_opex = cur["total_opex"].sum()

    prev_sales = prev["net_sales"].sum() if not prev.empty else None
    prev_gp = prev["gross_profit"].sum() if not prev.empty else None
    prev_op = prev["operating_profit"].sum() if not prev.empty else None

    def _comp(cur_v, prev_v):
        if prev_v and prev_v != 0:
            return [{"label": "前年", "value": round(cur_v / prev_v * 100, 1)}]
        return [{"label": "前年", "value": None}]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("全社売上", total_sales, prefix="฿", comparisons=_comp(total_sales, prev_sales))
    with c2:
        render_kpi_card("全社粗利", total_gp, prefix="฿", comparisons=_comp(total_gp, prev_gp))
    with c3:
        margin = total_gp / total_sales * 100 if total_sales else 0
        render_kpi_card("粗利率", margin, suffix="%", fmt=".1f")
    with c4:
        op_margin = total_op / total_sales * 100 if total_sales else 0
        render_kpi_card("営業利益率", op_margin, suffix="%", fmt=".1f", comparisons=_comp(total_op, prev_op))

    # =====================================================================
    # P&L Table — all stores side-by-side
    # =====================================================================
    st.divider()
    st.subheader(f"店舗別PL ({selected_ym})  単位: 千฿")

    # Build HTML table
    header = "<tr><th>科目</th>"
    for sid in stores:
        header += f"<th>{store_names[sid]}</th>"
    header += "<th>全社合計</th></tr>"

    rows_html = []
    for label, col in _PL_ROWS:
        is_pct = col.endswith("_pct")
        is_bold = col in ("gross_profit", "operating_profit", "total_opex", "net_sales")
        style = 'font-weight:700' if is_bold else ''
        indent = 'padding-left:24px' if label.startswith("  ") else ''
        row_style = f'style="{style};{indent}"' if style or indent else (f'style="{indent}"' if indent else '')

        row = f"<td {row_style}>{label.strip()}</td>"
        total_val = 0
        for sid in stores:
            store_row = cur[cur["store_id"] == sid]
            val = store_row[col].values[0] if not store_row.empty else None
            if is_pct:
                row += f"<td style='text-align:right'>{_fmt_pct(val)}</td>"
            elif col in ("operating_profit", "gross_profit"):
                row += f"<td style='text-align:right'>{_color_cell(val)}</td>"
            else:
                row += f"<td style='text-align:right'>{_fmt_amount(val)}</td>"
            if val is not None and not pd.isna(val) and not is_pct:
                total_val += val

        # Total column
        if is_pct:
            if col == "gross_margin_pct":
                tv = total_gp / total_sales * 100 if total_sales else 0
            elif col == "operating_margin_pct":
                tv = total_op / total_sales * 100 if total_sales else 0
            else:
                tv = 0
            row += f"<td style='text-align:right;font-weight:700'>{tv:.1f}%</td>"
        elif col in ("operating_profit", "gross_profit"):
            row += f"<td style='text-align:right;font-weight:700'>{_color_cell(total_val)}</td>"
        else:
            row += f"<td style='text-align:right;font-weight:700'>{_fmt_amount(total_val)}</td>"

        # Highlight rows
        bg = ""
        if col == "gross_profit":
            bg = "background:#F8FAFC;"
        elif col == "operating_profit":
            bg = "background:#F1F5F9;"

        rows_html.append(f'<tr style="border-bottom:1px solid #E2E8F0;{bg}">{row}</tr>')

    html = (
        '<div style="overflow-x:auto">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
        f"<thead style='background:#F1F5F9;color:#334155'>{header}</thead>"
        "<tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )
    html = html.replace("<th>", '<th style="padding:6px 10px;text-align:right;font-weight:600">')
    html = html.replace("<th style=\"padding:6px 10px;text-align:right;font-weight:600\">科目",
                         '<th style="padding:6px 10px;text-align:left;font-weight:600">科目')
    st.markdown(html, unsafe_allow_html=True)

    # =====================================================================
    # Expense Ratio Breakdown (stacked bar)
    # =====================================================================
    st.divider()
    st.subheader("経費構成比 (対売上比)")

    fig = go.Figure()
    for label, col, color in _EXPENSE_ITEMS:
        ratios = []
        for sid in stores:
            store_row = cur[cur["store_id"] == sid]
            if not store_row.empty:
                ratio = store_row[col].values[0] / store_row["net_sales"].values[0] * 100
                ratios.append(round(ratio, 1))
            else:
                ratios.append(0)
        fig.add_trace(go.Bar(
            name=label,
            x=[store_names[s] for s in stores],
            y=ratios,
            marker_color=color,
            text=[f"{r:.1f}%" for r in ratios],
            textposition="inside",
        ))
    fig.update_layout(
        barmode="stack",
        height=400,
        yaxis_title="対売上比 (%)",
        legend=dict(orientation="h", y=-0.15),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True)

    # =====================================================================
    # Operating Margin Trend
    # =====================================================================
    st.divider()
    st.subheader("営業利益率推移")

    trend = df[df["store_id"].isin(stores)].copy()
    trend["ym_disp"] = trend["ym"].apply(_ym_to_display)
    trend = trend.sort_values("ym")

    fig2 = go.Figure()
    for i, sid in enumerate(stores):
        store_data = trend[trend["store_id"] == sid]
        fig2.add_trace(go.Scatter(
            x=store_data["ym_disp"],
            y=store_data["operating_margin_pct"],
            name=store_names[sid],
            mode="lines+markers",
            line=dict(color=COLORS[i % len(COLORS)]),
        ))
    fig2.update_layout(
        height=400,
        yaxis_title="営業利益率 (%)",
        legend=dict(orientation="h", y=-0.15),
        **_CHART_LAYOUT,
    )
    fig2.update_xaxes(type="category", tickmode="linear")
    st.plotly_chart(fig2, use_container_width=True)

    # =====================================================================
    # YoY Comparison Table
    # =====================================================================
    if not prev.empty:
        st.divider()
        st.subheader(f"前年比較 ({prev_ym} → {selected_ym})")

        yoy_rows = []
        for sid in stores:
            c_row = cur[cur["store_id"] == sid]
            p_row = prev[prev["store_id"] == sid]
            if c_row.empty:
                continue
            c_sales = c_row["net_sales"].values[0]
            c_op = c_row["operating_profit"].values[0]
            p_sales = p_row["net_sales"].values[0] if not p_row.empty else None
            p_op = p_row["operating_profit"].values[0] if not p_row.empty else None

            yoy_rows.append({
                "店舗": store_names[sid],
                "当期売上(千฿)": f"{int(round(c_sales / 1000)):,}",
                "前年売上(千฿)": f"{int(round(p_sales / 1000)):,}" if p_sales else "--",
                "売上前年比": f"{round(c_sales / p_sales * 100)}%" if p_sales and p_sales > 0 else "--",
                "当期営業利益(千฿)": f"{int(round(c_op / 1000)):,}",
                "前年営業利益(千฿)": f"{int(round(p_op / 1000)):,}" if p_op else "--",
                "営業利益増減(千฿)": f"{int(round((c_op - p_op) / 1000)):,}" if p_op else "--",
            })

        if yoy_rows:
            st.dataframe(pd.DataFrame(yoy_rows), use_container_width=True, hide_index=True)
