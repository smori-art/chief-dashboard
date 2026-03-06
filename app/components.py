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

# Gray-based minimal color palette
COLORS_GRAY = [
    "#4a4a4a", "#7a7a7a", "#9e9e9e", "#b0b0b0", "#c8c8c8", "#d9d9d9",
]

_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#333", size=12),
    title_font=dict(size=14, color="#333"),
    margin=dict(l=10, r=10, t=40, b=10),
)


def render_sidebar_filters() -> dict[str, Any]:
    """
    Render common sidebar filters and return selected values.
    Used across all dashboard pages.
    """
    with st.sidebar:
        st.header("フィルタ")

        # Period
        ym_list = get_ym_list()
        selected_ym = st.selectbox(
            "期間（年月）",
            options=ym_list,
            index=0,
            key="filter_ym",
        )

        # Stores
        stores = get_store_list()
        store_options = {f"{sid} - {sname}": sid for sid, sname in stores}
        selected_stores_labels = st.multiselect(
            "店舗",
            options=list(store_options.keys()),
            default=list(store_options.keys()),
            key="filter_stores",
        )
        selected_store_ids = [store_options[s] for s in selected_stores_labels]

        # Departments
        depts = get_department_list()
        dept_options = {f"{dname}": did for did, dname in depts}
        selected_dept_labels = st.multiselect(
            "部門",
            options=list(dept_options.keys()),
            default=list(dept_options.keys()),
            key="filter_depts",
        )
        selected_dept_ids = [dept_options[d] for d in selected_dept_labels]

        # Sales type toggle
        sales_type = st.radio(
            "売上表示",
            options=["実売上 (Net)", "粗売上 (Gross)"],
            index=0,
            key="filter_sales_type",
            horizontal=True,
        )

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
) -> None:
    """Render a KPI metric card."""
    if isinstance(value, (int, float)):
        formatted_value = f"{prefix}{value:{fmt}}{suffix}"
    else:
        formatted_value = f"{prefix}{value}{suffix}"

    if delta is not None and isinstance(delta, (int, float)):
        delta_str = f"{delta:+{fmt}}{delta_suffix}"
        st.metric(label=label, value=formatted_value, delta=delta_str)
    else:
        st.metric(label=label, value=formatted_value)


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
        connector={"line": {"color": "#999"}},
        increasing={"marker": {"color": "#666"}},
        decreasing={"marker": {"color": "#aaa"}},
        totals={"marker": {"color": "#444"}},
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
