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
# Design tokens — cool minimal palette with blue accent
# ---------------------------------------------------------------------------
ACCENT = "#2563EB"          # primary blue
ACCENT_LIGHT = "#DBEAFE"    # blue-50
TEXT_PRIMARY = "#0F172A"     # slate-900
TEXT_SECONDARY = "#64748B"   # slate-500
BORDER = "#E2E8F0"          # slate-200
SURFACE = "#F8FAFC"         # slate-50

POSITIVE = "#16A34A"        # green-600
NEGATIVE = "#DC2626"        # red-600
POSITIVE_BG = "#F0FDF4"     # green-50
NEGATIVE_BG = "#FEF2F2"     # red-50
NEUTRAL_BG = "#F8FAFC"      # slate-50

# Chart color palette — distinguishable, cool tones
COLORS = [
    "#2563EB",  # blue
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#059669",  # emerald
    "#D97706",  # amber
    "#E11D48",  # rose
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
    delta: float | None = None,
    delta_suffix: str = "",
    prefix: str = "",
    suffix: str = "",
    fmt: str = ",.0f",
    sparkline: list[float] | None = None,
    target: float | None = None,
) -> None:
    """Render an enhanced KPI metric card with optional sparkline & progress bar.

    Args:
        sparkline: list of recent values to draw as an inline sparkline SVG.
        target: target value; if provided, shows a small progress bar.
    """
    if isinstance(value, (int, float)):
        formatted_value = f"{prefix}{value:{fmt}}{suffix}"
    else:
        formatted_value = f"{prefix}{value}{suffix}"

    if delta is not None and isinstance(delta, (int, float)):
        delta_str = f"{delta:+{fmt}}{delta_suffix}"
        st.metric(label=label, value=formatted_value, delta=delta_str)
    else:
        st.metric(label=label, value=formatted_value)

    # --- Optional sparkline (inline SVG) ---
    if sparkline and len(sparkline) >= 2:
        _render_sparkline(sparkline)

    # --- Optional target progress bar ---
    if target is not None and isinstance(value, (int, float)) and target > 0:
        pct = min(value / target, 1.5)
        bar_color = POSITIVE if pct >= 1.0 else ACCENT if pct >= 0.9 else NEGATIVE
        st.markdown(
            f'<div style="margin-top:4px">'
            f'<div style="background:{BORDER};border-radius:3px;height:5px;width:100%">'
            f'<div style="background:{bar_color};border-radius:3px;height:5px;'
            f'width:{min(pct * 100, 100):.0f}%"></div></div>'
            f'<span style="font-size:0.7rem;color:{TEXT_SECONDARY}">'
            f'達成率 {pct * 100:.0f}%</span></div>',
            unsafe_allow_html=True,
        )


def _render_sparkline(data: list[float], width: int = 100, height: int = 24) -> None:
    """Draw a tiny sparkline SVG inside the KPI card."""
    n = len(data)
    mn, mx = min(data), max(data)
    rng = mx - mn if mx != mn else 1
    padding = 2
    usable_w = width - padding * 2
    usable_h = height - padding * 2

    points = []
    for i, v in enumerate(data):
        x = padding + (i / (n - 1)) * usable_w
        y = padding + usable_h - ((v - mn) / rng) * usable_h
        points.append(f"{x:.1f},{y:.1f}")

    trend_color = POSITIVE if data[-1] >= data[0] else NEGATIVE
    polyline = " ".join(points)
    svg = (
        f'<svg width="{width}" height="{height}" style="display:block;margin-top:2px">'
        f'<polyline points="{polyline}" fill="none" stroke="{trend_color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
        f'r="2" fill="{trend_color}"/>'
        f'</svg>'
    )
    st.markdown(svg, unsafe_allow_html=True)


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
    fig.update_layout(
        xaxis_title="",
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
        increasing={"marker": {"color": POSITIVE}},
        decreasing={"marker": {"color": NEGATIVE}},
        totals={"marker": {"color": ACCENT}},
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
