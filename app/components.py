"""
Shared UI components: filters, KPI cards, charts.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.data import get_department_list, get_store_list, get_ym_list

# ---------------------------------------------------------------------------
# Design tokens — cool minimal palette with 臙脂 accent
# ---------------------------------------------------------------------------
ACCENT = "#9B2335"          # 臙脂 (えんじ)
ACCENT_LIGHT = "#FDF2F4"    # 臙脂 tint
TEXT_PRIMARY = "#0F172A"     # slate-900
TEXT_SECONDARY = "#64748B"   # slate-500
BORDER = "#E2E8F0"          # slate-200
SURFACE = "#F8FAFC"         # slate-50

POSITIVE = "#16A34A"        # green-600
NEGATIVE = "#DC2626"        # red-600
POSITIVE_BG = "#F0FDF4"     # green-50
NEGATIVE_BG = "#FEF2F2"     # red-50
NEUTRAL_BG = "#F8FAFC"      # slate-50

# Chart color palette — muted / low-saturation tones
COLORS = [
    "#C4838F",  # muted rose
    "#7BA3C9",  # muted blue
    "#7BBF8E",  # muted green
    "#C9B36A",  # muted gold
    "#9E8DBF",  # muted violet
    "#6FB5BF",  # muted teal
    "#C49570",  # muted terracotta
    "#B889A0",  # muted mauve
]

# Keep backward-compatible alias
COLORS_GRAY = COLORS

_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color=TEXT_PRIMARY, size=12),
    title_font=dict(size=13, color=TEXT_SECONDARY, family="Inter, -apple-system, sans-serif"),
    margin=dict(l=10, r=10, t=40, b=10),
    hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=BORDER),
)


def render_sidebar_filters() -> dict[str, Any]:
    """
    Render common sidebar filters and return selected values.
    Uses a compact expander to keep the sidebar clean.
    """
    with st.sidebar:
        # Period — always visible (most-used filter)
        ym_list = get_ym_list()
        selected_ym = st.selectbox(
            "期間",
            options=ym_list,
            index=0,
            key="filter_ym",
        )

        # Sales type toggle — compact pills
        sales_type = st.radio(
            "売上種別",
            options=["実売上 (Net)", "粗売上 (Gross)"],
            index=0,
            key="filter_sales_type",
            horizontal=True,
        )

        # Stores & Departments inside collapsible section
        with st.expander("店舗・部門を絞り込む", expanded=False):
            stores = get_store_list()
            store_options = {f"{sid} - {sname}": sid for sid, sname in stores}
            selected_stores_labels = st.multiselect(
                "店舗",
                options=list(store_options.keys()),
                default=list(store_options.keys()),
                key="filter_stores",
            )

            depts = get_department_list()
            dept_options = {f"{dname}": did for did, dname in depts}
            selected_dept_labels = st.multiselect(
                "部門",
                options=list(dept_options.keys()),
                default=list(dept_options.keys()),
                key="filter_depts",
            )

        selected_store_ids = [store_options[s] for s in selected_stores_labels]
        selected_dept_ids = [dept_options[d] for d in selected_dept_labels]

        st.divider()

    return {
        "ym": selected_ym,
        "store_ids": selected_store_ids,
        "dept_ids": selected_dept_ids,
        "sales_type": "net" if "Net" in sales_type else "gross",
    }


def filter_dataframe(
    df: pd.DataFrame,
    filters: dict[str, Any],
    ym_col: str = "ym",
) -> pd.DataFrame:
    """Apply common filters to a DataFrame."""
    filtered = df.copy()

    if ym_col in filtered.columns and filters.get("ym"):
        filtered = filtered[filtered[ym_col] == filters["ym"]]

    if "store_id" in filtered.columns and filters.get("store_ids"):
        filtered = filtered[filtered["store_id"].isin(filters["store_ids"])]

    if "dept_id" in filtered.columns and filters.get("dept_ids"):
        filtered = filtered[filtered["dept_id"].isin(filters["dept_ids"])]

    return filtered


def get_sales_column(filters: dict[str, Any]) -> str:
    """Get the appropriate sales column based on filter selection."""
    return "net_sales_ex_tax" if filters["sales_type"] == "net" else "gross_sales_ex_tax"


def render_kpi_card(
    label: str,
    value: float | int | str,
    prefix: str = "",
    suffix: str = "",
    fmt: str = ",.0f",
    comparisons: list[dict[str, Any]] | None = None,
    sparkline: list[float] | None = None,
    target: float | None = None,
    # Legacy params kept for backward compatibility
    delta: float | None = None,
    delta_suffix: str = "",
) -> None:
    """Render a fully custom KPI card via HTML.

    Args:
        comparisons: list of {"label": "前年", "value": 103.5} dicts.
            value is a percentage (100 = flat). Shown as colored badges.
        sparkline: recent values drawn as an inline SVG sparkline.
        target: if set, show a progress bar vs target.
        delta/delta_suffix: legacy single-delta (used when comparisons is None).
    """
    # Format main value
    if isinstance(value, (int, float)):
        formatted_value = f"{prefix}{value:{fmt}}{suffix}"
    else:
        formatted_value = f"{prefix}{value}{suffix}"

    # Build comparison badges HTML
    badges_html = ""
    if comparisons:
        badges = []
        for comp in comparisons:
            pct = comp.get("value")
            lbl = comp.get("label", "")
            if pct is None:
                badges.append(
                    f'<span style="display:inline-block;font-size:0.65rem;'
                    f'color:{TEXT_SECONDARY};background:#F1F5F9;'
                    f'border-radius:3px;padding:1px 5px;margin-right:3px">'
                    f'{lbl} --</span>'
                )
                continue
            color = POSITIVE if pct >= 100 else NEGATIVE
            bg = POSITIVE_BG if pct >= 100 else NEGATIVE_BG
            arrow = "\u25B2" if pct >= 100 else "\u25BC"
            badges.append(
                f'<span style="display:inline-block;font-size:0.65rem;'
                f'color:{color};background:{bg};'
                f'border-radius:3px;padding:1px 5px;margin-right:3px">'
                f'{lbl}{arrow}{pct:.1f}%</span>'
            )
        badges_html = (
            '<div style="margin-top:4px;line-height:1.6">'
            + "".join(badges)
            + "</div>"
        )
    elif delta is not None and isinstance(delta, (int, float)):
        # Legacy single delta
        color = POSITIVE if delta >= 0 else NEGATIVE
        arrow = "\u25B2" if delta >= 0 else "\u25BC"
        badges_html = (
            f'<div style="margin-top:4px">'
            f'<span style="font-size:0.75rem;color:{color}">'
            f'{arrow} {delta:+{fmt}}{delta_suffix}</span></div>'
        )

    # Sparkline SVG
    spark_svg = ""
    if sparkline and len(sparkline) >= 2:
        spark_svg = _build_sparkline_svg(sparkline)

    # Target progress bar
    target_html = ""
    if target is not None and isinstance(value, (int, float)) and target > 0:
        pct = min(value / target, 1.5)
        bar_color = POSITIVE if pct >= 1.0 else ACCENT if pct >= 0.9 else NEGATIVE
        target_html = (
            f'<div style="margin-top:5px">'
            f'<div style="background:{BORDER};border-radius:3px;height:4px;width:100%">'
            f'<div style="background:{bar_color};border-radius:3px;height:4px;'
            f'width:{min(pct * 100, 100):.0f}%"></div></div>'
            f'<span style="font-size:0.65rem;color:{TEXT_SECONDARY}">'
            f'達成率 {pct * 100:.0f}%</span></div>'
        )

    # Render full card as one HTML block
    st.markdown(
        f'<div style="background:#fff;border:1px solid {BORDER};border-radius:10px;'
        f'padding:16px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.04);min-height:130px">'
        f'<div style="font-size:0.68rem;font-weight:600;color:{TEXT_SECONDARY};'
        f'text-transform:uppercase;letter-spacing:0.06em">{label}</div>'
        f'<div style="font-size:1.45rem;font-weight:700;color:{TEXT_PRIMARY};'
        f'margin-top:4px">{formatted_value}</div>'
        f'{badges_html}'
        f'{spark_svg}'
        f'{target_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _build_sparkline_svg(
    data: list[float], width: int = 110, height: int = 28,
) -> str:
    """Return an inline SVG sparkline string."""
    n = len(data)
    mn, mx = min(data), max(data)
    rng = mx - mn if mx != mn else 1
    pad = 2
    uw = width - pad * 2
    uh = height - pad * 2

    points = []
    for i, v in enumerate(data):
        x = pad + (i / (n - 1)) * uw
        y = pad + uh - ((v - mn) / rng) * uh
        points.append(f"{x:.1f},{y:.1f}")

    color = POSITIVE if data[-1] >= data[0] else NEGATIVE
    poly = " ".join(points)
    last_x = points[-1].split(",")[0]
    last_y = points[-1].split(",")[1]
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="display:block;margin-top:4px">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2" fill="{color}"/>'
        f'</svg>'
    )


def render_kpi_row(kpis: list[dict[str, Any]], cols: int = 4) -> None:
    """Render a row of KPI cards."""
    columns = st.columns(cols)
    for i, kpi in enumerate(kpis):
        with columns[i % cols]:
            render_kpi_card(**kpi)


def chart_bar_composition(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    title: str,
    color_col: str | None = None,
    orientation: str = "h",
) -> go.Figure:
    """Create a horizontal bar chart for composition analysis."""
    fig = px.bar(
        df.sort_values(value_col, ascending=True),
        x=value_col,
        y=category_col,
        orientation=orientation,
        color=color_col,
        title=title,
        text=value_col,
        color_discrete_sequence=COLORS_GRAY,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(300, len(df) * 35),
        showlegend=False,
        **_CHART_LAYOUT,
    )
    return fig


def chart_line_trend(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str | None = None,
    title: str = "",
    y_title: str = "",
    x_tick_format: str | None = None,
    x_dtick: str | None = None,
) -> go.Figure:
    """Create a line chart for trend analysis."""
    fig = px.line(
        df.sort_values(x_col),
        x=x_col,
        y=y_col,
        color=color_col,
        title=title,
        markers=True,
        color_discrete_sequence=COLORS_GRAY,
    )
    xaxis_opts: dict = {"title": ""}
    if x_tick_format:
        xaxis_opts["tickformat"] = x_tick_format
    if x_dtick:
        xaxis_opts["dtick"] = x_dtick
    fig.update_layout(
        xaxis=xaxis_opts,
        yaxis_title=y_title,
        height=400,
        **_CHART_LAYOUT,
    )
    return fig


def chart_waterfall(
    categories: list[str],
    values: list[float],
    title: str = "",
) -> go.Figure:
    """Create a waterfall chart for factor decomposition."""
    measures = ["absolute"] + ["relative"] * (len(categories) - 2) + ["total"]
    if len(categories) <= 2:
        measures = ["absolute"] * len(categories)

    fig = go.Figure(go.Waterfall(
        name="",
        orientation="v",
        measure=measures,
        x=categories,
        y=values,
        textposition="outside",
        text=[f"{v:+,.0f}" if i > 0 else f"{v:,.0f}"
              for i, v in enumerate(values)],
        connector={"line": {"color": BORDER}},
        increasing={"marker": {"color": "#7BBF8E"}},
        decreasing={"marker": {"color": "#C4838F"}},
        totals={"marker": {"color": "#7BA3C9"}},
    ))
    fig.update_layout(
        title=title,
        height=400,
        showlegend=False,
        **_CHART_LAYOUT,
    )
    return fig


def chart_heatmap(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    value_col: str,
    title: str = "",
    color_scale: str = "RdYlGn",
) -> go.Figure:
    """Create a heatmap chart."""
    pivot = df.pivot_table(index=y_col, columns=x_col, values=value_col, aggfunc="mean")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=color_scale,
        text=[[f"{v:.1f}" if pd.notna(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont={"size": 10},
    ))
    fig.update_layout(
        title=title,
        height=max(300, len(pivot) * 40),
        **_CHART_LAYOUT,
    )
    return fig


def render_data_table(
    df: pd.DataFrame,
    title: str = "",
    height: int = 400,
) -> None:
    """Render a formatted data table."""
    if title:
        st.subheader(title)
    st.dataframe(
        df,
        height=height,
        use_container_width=True,
        hide_index=True,
    )
