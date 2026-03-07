"""
Data access layer for Streamlit.
Provides cached data loading from BigQuery with mock data fallback.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from loguru import logger

from app.config import get_config

try:
    from google.cloud import bigquery

    HAS_BQ = True
except ImportError:
    HAS_BQ = False


def _get_bq_client() -> Any:
    """Get BigQuery client (cached)."""
    if not HAS_BQ:
        return None
    try:
        project_id = os.getenv("GCP_PROJECT_ID")
        return bigquery.Client(project=project_id)
    except Exception as e:
        logger.warning(f"BigQuery client creation failed: {e}")
        return None


def _run_query(query: str, params: list | None = None) -> pd.DataFrame:
    """Execute a BigQuery query and return results as DataFrame."""
    client = _get_bq_client()
    if client is None:
        return pd.DataFrame()

    config = get_config()
    # Replace template variables
    query = query.replace("${PROJECT_ID}", config.gcp_project_id)
    query = query.replace("${DATASET_RAW}", config.bq_dataset_raw)
    query = query.replace("${DATASET_STG}", config.bq_dataset_stg)
    query = query.replace("${DATASET_MART}", config.bq_dataset_mart)

    try:
        if params:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            return client.query(query, job_config=job_config).to_dataframe()
        return client.query(query).to_dataframe()
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return pd.DataFrame()


# ===========================================================================
# Demo/Mock data generators (used when BigQuery is not available)
# ===========================================================================

def _generate_demo_dates(months: int = 24) -> list[str]:
    """Generate year-month strings for demo data."""
    today = date.today()
    result = []
    year = today.year
    month = today.month
    for _ in range(months):
        result.append(f"{year}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return sorted(set(result))


def _generate_demo_sales_monthly() -> pd.DataFrame:
    """Generate demo monthly sales data."""
    np.random.seed(42)
    stores = [
        ("S001", "バンコク中央店"),
        ("S002", "チェンマイ店"),
        ("S003", "パタヤ店"),
        ("S004", "プーケット店"),
    ]
    depts = [
        ("food", "食品"),
        ("produce", "青果"),
        ("seafood", "鮮魚"),
        ("meat", "精肉"),
        ("deli", "惣菜"),
        ("store_mgmt", "店舗管理"),
    ]
    yms = _generate_demo_dates(24)

    rows = []
    for ym in yms:
        year = int(ym[:4])
        month = int(ym[5:7])
        for store_id, store_name in stores:
            total_gross = 0
            total_net = 0
            total_profit = 0
            store_rows = []
            for dept_id, dept_name in depts:
                base = np.random.uniform(500_000, 5_000_000)
                # Add seasonality
                seasonal = 1.0 + 0.1 * np.sin(month * np.pi / 6)
                gross_sales = round(base * seasonal, 2)
                discount_rate = np.random.uniform(0.02, 0.08)
                discount = round(gross_sales * discount_rate, 2)
                net_sales = round(gross_sales - discount, 2)
                cost_rate = np.random.uniform(0.60, 0.80)
                cogs = round(net_sales * cost_rate, 2)
                gross_profit = round(net_sales - cogs, 2)
                margin_pct = round(gross_profit / net_sales * 100, 2) if net_sales else 0
                qty = int(np.random.uniform(1000, 20000))
                receipts = int(np.random.uniform(200, 3000))

                total_gross += gross_sales
                total_net += net_sales
                total_profit += gross_profit

                store_rows.append({
                    "ym": ym,
                    "year": year,
                    "month": month,
                    "store_id": store_id,
                    "store_name": store_name,
                    "dept_id": dept_id,
                    "dept_name": dept_name,
                    "gross_sales_ex_tax": gross_sales,
                    "net_sales_ex_tax": net_sales,
                    "discount_amount_ex_tax": discount,
                    "qty": qty,
                    "receipts": receipts,
                    "refund_amount": round(net_sales * 0.005, 2),
                    "net_sales_after_refund": round(net_sales * 0.995, 2),
                    "cogs": cogs,
                    "gross_profit": gross_profit,
                    "gross_margin_pct": margin_pct,
                    "discount_rate_pct": round(discount_rate * 100, 2),
                })

            # Calculate composition percentages
            for row in store_rows:
                row["sales_composition_pct"] = round(
                    row["net_sales_ex_tax"] / total_net * 100, 2
                ) if total_net else 0
                row["profit_composition_pct"] = round(
                    row["gross_profit"] / total_profit * 100, 2
                ) if total_profit else 0
            rows.extend(store_rows)

    df = pd.DataFrame(rows)

    # Calculate YoY by shifting year
    prev_lookup = df[["ym", "year", "month", "store_id", "dept_id",
                       "gross_sales_ex_tax", "net_sales_ex_tax",
                       "gross_profit", "gross_margin_pct"]].copy()
    prev_lookup["join_ym"] = prev_lookup.apply(
        lambda r: f"{int(r['year']) + 1}-{int(r['month']):02d}", axis=1
    )
    prev_lookup = prev_lookup.rename(columns={
        "gross_sales_ex_tax": "gross_sales_prev_year",
        "net_sales_ex_tax": "net_sales_prev_year",
        "gross_profit": "gross_profit_prev_year",
        "gross_margin_pct": "gross_margin_prev_year",
    })

    df = df.merge(
        prev_lookup[["join_ym", "store_id", "dept_id",
                      "gross_sales_prev_year", "net_sales_prev_year",
                      "gross_profit_prev_year", "gross_margin_prev_year"]],
        left_on=["ym", "store_id", "dept_id"],
        right_on=["join_ym", "store_id", "dept_id"],
        how="left",
    )
    df.drop(columns=["join_ym"], inplace=True, errors="ignore")

    df["gross_sales_yoy"] = df["gross_sales_ex_tax"] - df["gross_sales_prev_year"].fillna(0)
    df["net_sales_yoy"] = df["net_sales_ex_tax"] - df["net_sales_prev_year"].fillna(0)
    df["gross_profit_yoy"] = df["gross_profit"] - df["gross_profit_prev_year"].fillna(0)
    df["gross_margin_yoy_diff"] = df["gross_margin_pct"] - df["gross_margin_prev_year"].fillna(0)

    return df


def _generate_demo_category_data() -> pd.DataFrame:
    """Generate demo category drilldown data."""
    np.random.seed(123)
    categories = {
        "food": [
            ("加工食品", "調味料", "醤油"),
            ("加工食品", "調味料", "味噌"),
            ("加工食品", "缶詰", "ツナ缶"),
            ("飲料", "茶飲料", "緑茶"),
            ("飲料", "炭酸飲料", "コーラ"),
            ("菓子", "スナック", "ポテトチップス"),
            ("菓子", "チョコレート", "板チョコ"),
        ],
        "produce": [
            ("野菜", "葉物", "レタス"),
            ("野菜", "根菜", "にんじん"),
            ("果物", "柑橘", "オレンジ"),
            ("果物", "熱帯果物", "マンゴー"),
        ],
        "seafood": [
            ("鮮魚", "白身魚", "鯛"),
            ("鮮魚", "赤身魚", "マグロ"),
            ("貝類", "二枚貝", "アサリ"),
        ],
        "meat": [
            ("牛肉", "和牛", "サーロイン"),
            ("豚肉", "国産豚", "ロース"),
            ("鶏肉", "国産鶏", "もも肉"),
        ],
        "deli": [
            ("弁当", "和食弁当", "幕の内"),
            ("サラダ", "野菜サラダ", "シーザー"),
            ("揚げ物", "フライ", "コロッケ"),
        ],
    }

    yms = _generate_demo_dates(12)
    stores = ["S001", "S002", "S003", "S004"]
    rows = []

    for ym in yms:
        for store_id in stores:
            for dept_id, cats in categories.items():
                for cat_l, cat_m, cat_s in cats:
                    base = np.random.uniform(50_000, 500_000)
                    gross = round(base, 2)
                    discount = round(gross * np.random.uniform(0.01, 0.10), 2)
                    net = round(gross - discount, 2)
                    cogs = round(net * np.random.uniform(0.55, 0.82), 2)
                    profit = round(net - cogs, 2)
                    rows.append({
                        "ym": ym,
                        "store_id": store_id,
                        "dept_id": dept_id,
                        "cat_l": cat_l,
                        "cat_m": cat_m,
                        "cat_s": cat_s,
                        "gross_sales_ex_tax": gross,
                        "net_sales_ex_tax": net,
                        "discount_amount_ex_tax": discount,
                        "qty": int(np.random.uniform(100, 5000)),
                        "cogs": cogs,
                        "gross_profit": profit,
                        "gross_margin_pct": round(profit / net * 100, 2) if net else 0,
                        "discount_rate_pct": round(discount / gross * 100, 2) if gross else 0,
                    })

    return pd.DataFrame(rows)


def _generate_demo_oos_data() -> pd.DataFrame:
    """Generate demo OOS (out-of-stock) data."""
    np.random.seed(456)
    stores = ["S001", "S002", "S003", "S004"]
    skus = [f"SKU{i:04d}" for i in range(1, 51)]
    depts = ["food", "produce", "seafood", "meat", "deli"]

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(30)]

    rows = []
    for d in dates:
        for store_id in stores:
            for sku in skus:
                dept = np.random.choice(depts)
                expected = np.random.uniform(5, 50)
                # 10% chance of OOS
                if np.random.random() < 0.10:
                    actual = round(expected * np.random.uniform(0, 0.15), 1)
                    is_oos = True
                else:
                    actual = round(expected * np.random.uniform(0.5, 1.5), 1)
                    is_oos = False

                rows.append({
                    "date": d,
                    "store_id": store_id,
                    "sku": sku,
                    "dept_id": dept,
                    "product_name": f"商品{sku}",
                    "expected_qty": round(expected, 1),
                    "actual_qty": actual,
                    "is_oos_suspect": is_oos,
                    "opportunity_loss_amount": round(
                        (expected - actual) * np.random.uniform(50, 200), 2
                    ) if is_oos else 0,
                    "dow": d.weekday() + 1,
                })

    return pd.DataFrame(rows)


def _generate_demo_forecast() -> pd.DataFrame:
    """Generate demo forecast data."""
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    stores = ["S001", "S002", "S003", "S004"]
    depts = ["food", "produce", "seafood", "meat", "deli", "store_mgmt"]

    rows = []
    for store_id in stores:
        for dept_id in depts:
            actual = np.random.uniform(1_000_000, 10_000_000)
            elapsed = today.day
            total = 30
            forecast = round(actual / elapsed * total, 2) if elapsed >= 7 else None
            rows.append({
                "ym": current_ym,
                "store_id": store_id,
                "dept_id": dept_id,
                "actual_to_date": round(actual, 2),
                "elapsed_days": elapsed,
                "total_days": total,
                "forecast_sales": forecast,
                "forecast_method": "linear_extrapolation",
            })

    return pd.DataFrame(rows)


# ===========================================================================
# Cached data loading functions
# ===========================================================================

@st.cache_data(ttl=300)
def load_sales_monthly() -> pd.DataFrame:
    """Load monthly sales KPI data."""
    config = get_config()
    client = _get_bq_client()

    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_kpi_sales_monthly`
            ORDER BY ym DESC, store_id, dept_id
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"BQ query failed, using demo data: {e}")

    return _generate_demo_sales_monthly()


@st.cache_data(ttl=300)
def load_category_drilldown() -> pd.DataFrame:
    """Load category drilldown data."""
    config = get_config()
    client = _get_bq_client()

    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_kpi_category_drilldown`
            ORDER BY ym DESC, store_id, dept_id, cat_l, cat_m, cat_s
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"BQ query failed, using demo data: {e}")

    return _generate_demo_category_data()


@st.cache_data(ttl=300)
def load_oos_data() -> pd.DataFrame:
    """Load OOS analysis data."""
    config = get_config()
    client = _get_bq_client()

    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_kpi_oos_receipt`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            ORDER BY date DESC, store_id, sku
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"BQ query failed, using demo data: {e}")

    return _generate_demo_oos_data()


@st.cache_data(ttl=300)
def load_forecast() -> pd.DataFrame:
    """Load forecast data."""
    config = get_config()
    client = _get_bq_client()

    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_kpi_forecast`
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"BQ query failed, using demo data: {e}")

    return _generate_demo_forecast()


def _generate_demo_timeband_data() -> pd.DataFrame:
    """Generate demo time-band sales data (hourly by department)."""
    np.random.seed(700)
    stores = ["S001", "S002", "S003", "S004"]
    depts = ["food", "produce", "seafood", "meat", "deli"]
    dept_names = {"food": "食品", "produce": "青果", "seafood": "鮮魚", "meat": "精肉", "deli": "惣菜"}
    timebands = [
        ("09-10", 0.5), ("10-11", 0.8), ("11-12", 1.2), ("12-13", 1.0),
        ("13-14", 0.7), ("14-15", 0.6), ("15-16", 0.9), ("16-17", 1.3),
        ("17-18", 1.5), ("18-19", 1.4), ("19-20", 1.0), ("20-21", 0.6),
    ]
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(30)]

    rows = []
    for d in dates:
        for store_id in stores:
            for dept_id in depts:
                for tb, weight in timebands:
                    # Deli peaks in evening
                    dept_weight = 1.8 if dept_id == "deli" and tb >= "17" else 1.0
                    base = np.random.uniform(20_000, 200_000) * weight * dept_weight
                    rows.append({
                        "date": d,
                        "store_id": store_id,
                        "dept_id": dept_id,
                        "dept_name": dept_names[dept_id],
                        "timeband": tb,
                        "net_sales": round(base, 2),
                        "qty": int(base / np.random.uniform(50, 150)),
                        "receipts": int(np.random.uniform(10, 200) * weight),
                        "dow": d.weekday() + 1,
                    })
    return pd.DataFrame(rows)


def _generate_demo_basket_data() -> pd.DataFrame:
    """Generate demo basket (co-purchase) data."""
    np.random.seed(800)
    products = [
        ("醤油", "food"), ("味噌", "food"), ("緑茶", "food"), ("コーラ", "food"),
        ("ポテトチップス", "food"), ("レタス", "produce"), ("にんじん", "produce"),
        ("マグロ", "seafood"), ("鯛", "seafood"), ("ロース", "meat"),
        ("もも肉", "meat"), ("幕の内", "deli"), ("コロッケ", "deli"),
        ("板チョコ", "food"), ("オレンジ", "produce"), ("アサリ", "seafood"),
    ]
    stores = ["S001", "S002", "S003", "S004"]
    today = date.today()

    rows = []
    receipt_id = 1000
    for day_offset in range(30):
        d = today - timedelta(days=day_offset)
        for store_id in stores:
            n_receipts = np.random.randint(50, 200)
            for _ in range(n_receipts):
                receipt_id += 1
                n_items = np.random.randint(2, 8)
                basket = np.random.choice(len(products), size=min(n_items, len(products)), replace=False)
                for idx in basket:
                    name, dept = products[idx]
                    price = np.random.uniform(30, 500)
                    qty = np.random.randint(1, 5)
                    rows.append({
                        "date": d,
                        "store_id": store_id,
                        "receipt_id": f"R{receipt_id:08d}",
                        "product_name": name,
                        "dept_id": dept,
                        "qty": qty,
                        "net_sales": round(price * qty, 2),
                    })
    return pd.DataFrame(rows)


def _generate_demo_budget_data() -> pd.DataFrame:
    """Generate demo budget data."""
    np.random.seed(900)
    stores = ["S001", "S002", "S003", "S004"]
    depts = ["food", "produce", "seafood", "meat", "deli", "store_mgmt"]
    yms = _generate_demo_dates(12)

    rows = []
    for ym in yms:
        for store_id in stores:
            for dept_id in depts:
                budget_sales = round(np.random.uniform(800_000, 6_000_000), 2)
                budget_profit = round(budget_sales * np.random.uniform(0.18, 0.35), 2)
                rows.append({
                    "ym": ym,
                    "store_id": store_id,
                    "dept_id": dept_id,
                    "budget_sales": budget_sales,
                    "budget_gross_profit": budget_profit,
                    "budget_margin_pct": round(budget_profit / budget_sales * 100, 1),
                })
    return pd.DataFrame(rows)


def _generate_demo_daily_sales() -> pd.DataFrame:
    """Generate demo daily sales data."""
    np.random.seed(950)
    stores = ["S001", "S002", "S003", "S004"]
    store_names = {"S001": "バンコク中央店", "S002": "チェンマイ店", "S003": "パタヤ店", "S004": "プーケット店"}
    depts = ["food", "produce", "seafood", "meat", "deli"]
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(90)]

    rows = []
    for d in dates:
        dow = d.weekday() + 1
        # Weekend boost
        dow_factor = 1.3 if dow >= 6 else 1.0
        for store_id in stores:
            for dept_id in depts:
                base = np.random.uniform(50_000, 400_000) * dow_factor
                net_sales = round(base, 2)
                gross_profit = round(net_sales * np.random.uniform(0.18, 0.35), 2)
                rows.append({
                    "date": d,
                    "store_id": store_id,
                    "store_name": store_names[store_id],
                    "dept_id": dept_id,
                    "net_sales": net_sales,
                    "gross_profit": gross_profit,
                    "qty": int(np.random.uniform(100, 3000)),
                    "receipts": int(np.random.uniform(30, 500) * dow_factor),
                    "dow": dow,
                    "dow_name": ["月", "火", "水", "木", "金", "土", "日"][dow - 1],
                })
    return pd.DataFrame(rows)


def _generate_demo_discount_detail() -> pd.DataFrame:
    """Generate demo discount detail data."""
    np.random.seed(1000)
    stores = ["S001", "S002", "S003", "S004"]
    depts = ["food", "produce", "seafood", "meat", "deli"]
    reasons = [
        ("期限間近", 0.35), ("見切り品", 0.25), ("販促値引", 0.20),
        ("破損品", 0.08), ("従業員割引", 0.07), ("その他", 0.05),
    ]
    timebands = ["09-12", "12-15", "15-18", "18-21"]
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(30)]

    rows = []
    for d in dates:
        for store_id in stores:
            for dept_id in depts:
                base_total = np.random.uniform(30_000, 200_000)
                for reason, ratio in reasons:
                    for tb in timebands:
                        # Evening discount spike for expiry/markdown
                        time_weight = 2.5 if tb == "18-21" and reason in ("期限間近", "見切り品") else 1.0
                        amount = round(base_total * ratio * 0.25 * time_weight * np.random.uniform(0.5, 1.5), 2)
                        count = max(1, int(amount / np.random.uniform(20, 100)))
                        rows.append({
                            "date": d,
                            "store_id": store_id,
                            "dept_id": dept_id,
                            "discount_reason": reason,
                            "timeband": tb,
                            "discount_amount": amount,
                            "discount_count": count,
                            "avg_discount": round(amount / count, 2),
                        })
    return pd.DataFrame(rows)


def _generate_demo_waste_data() -> pd.DataFrame:
    """Generate demo waste/loss data."""
    np.random.seed(1100)
    stores = ["S001", "S002", "S003", "S004"]
    store_names = {"S001": "バンコク中央店", "S002": "チェンマイ店", "S003": "パタヤ店", "S004": "プーケット店"}
    depts = [
        ("produce", "青果"), ("seafood", "鮮魚"), ("meat", "精肉"), ("deli", "惣菜"), ("food", "食品"),
    ]
    waste_types = ["期限切れ廃棄", "破損廃棄", "調理ロス", "棚卸差異"]
    yms = _generate_demo_dates(12)

    rows = []
    for ym in yms:
        for store_id in stores:
            for dept_id, dept_name in depts:
                # Perishables have higher waste
                base_rate = {"produce": 0.06, "seafood": 0.05, "meat": 0.04, "deli": 0.08, "food": 0.015}
                dept_sales = np.random.uniform(500_000, 3_000_000)
                for wtype in waste_types:
                    type_ratio = {"期限切れ廃棄": 0.5, "破損廃棄": 0.15, "調理ロス": 0.25, "棚卸差異": 0.1}
                    waste_amount = round(
                        dept_sales * base_rate[dept_id] * type_ratio[wtype] * np.random.uniform(0.5, 1.5), 2
                    )
                    rows.append({
                        "ym": ym,
                        "store_id": store_id,
                        "store_name": store_names[store_id],
                        "dept_id": dept_id,
                        "dept_name": dept_name,
                        "waste_type": wtype,
                        "waste_amount": waste_amount,
                        "waste_qty": int(waste_amount / np.random.uniform(30, 150)),
                        "dept_sales": round(dept_sales, 2),
                        "waste_rate_pct": round(waste_amount / dept_sales * 100, 2),
                    })
    return pd.DataFrame(rows)


def _generate_demo_store_pl() -> pd.DataFrame:
    """Generate demo store-level P&L data."""
    np.random.seed(1200)
    stores = [
        ("S001", "バンコク中央店"),
        ("S002", "チェンマイ店"),
        ("S003", "パタヤ店"),
        ("S004", "プーケット店"),
    ]
    yms = _generate_demo_dates(24)

    rows = []
    for ym in yms:
        month = int(ym[5:7])
        seasonal = 1.0 + 0.08 * np.sin(month * np.pi / 6)
        for store_id, store_name in stores:
            # Store size factor
            size_factor = {"S001": 1.5, "S002": 0.8, "S003": 1.0, "S004": 0.7}[store_id]
            net_sales = round(np.random.uniform(8_000_000, 15_000_000) * size_factor * seasonal, 2)
            cogs_rate = np.random.uniform(0.65, 0.75)
            cogs = round(net_sales * cogs_rate, 2)
            gross_profit = round(net_sales - cogs, 2)

            # Operating expenses
            personnel = round(net_sales * np.random.uniform(0.08, 0.12), 2)
            rent = round(np.random.uniform(200_000, 600_000) * size_factor, 2)
            utility = round(np.random.uniform(80_000, 200_000) * size_factor, 2)
            depreciation = round(np.random.uniform(50_000, 150_000) * size_factor, 2)
            other = round(net_sales * np.random.uniform(0.02, 0.04), 2)
            total_opex = personnel + rent + utility + depreciation + other
            op_profit = round(gross_profit - total_opex, 2)

            rows.append({
                "ym": ym,
                "store_id": store_id,
                "store_name": store_name,
                "net_sales": net_sales,
                "cogs": cogs,
                "gross_profit": gross_profit,
                "gross_margin_pct": round(gross_profit / net_sales * 100, 1) if net_sales else 0,
                "personnel_expense": personnel,
                "rent_expense": rent,
                "utility_expense": utility,
                "depreciation_expense": depreciation,
                "other_opex": other,
                "total_opex": round(total_opex, 2),
                "operating_profit": op_profit,
                "operating_margin_pct": round(op_profit / net_sales * 100, 1) if net_sales else 0,
                "personnel_ratio_pct": round(personnel / net_sales * 100, 1),
                "rent_ratio_pct": round(rent / net_sales * 100, 1),
                "utility_ratio_pct": round(utility / net_sales * 100, 1),
                "depreciation_ratio_pct": round(depreciation / net_sales * 100, 1),
                "other_opex_ratio_pct": round(other / net_sales * 100, 1),
                "total_opex_ratio_pct": round(total_opex / net_sales * 100, 1),
            })

    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_store_pl() -> pd.DataFrame:
    """Load store-level P&L data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_store_pl_monthly`
            ORDER BY ym DESC, store_id
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Store PL query failed, using demo data: {e}")
    return _generate_demo_store_pl()


@st.cache_data(ttl=60)
def load_import_history() -> pd.DataFrame:
    """Load import audit log."""
    config = get_config()
    client = _get_bq_client()

    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_raw}.import_audit_log`
            ORDER BY imported_at DESC
            LIMIT 100
        """
        try:
            return client.query(query).to_dataframe()
        except Exception as e:
            logger.warning(f"Import history query failed: {e}")

    # Return empty DataFrame with expected columns
    return pd.DataFrame(columns=[
        "import_id", "source_type", "source_file", "file_checksum",
        "imported_at", "imported_by", "row_count", "status",
        "error_message", "error_rows",
    ])


@st.cache_data(ttl=300)
def load_timeband_data() -> pd.DataFrame:
    """Load time-band sales data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_kpi_timeband`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Timeband query failed, using demo data: {e}")
    return _generate_demo_timeband_data()


@st.cache_data(ttl=300)
def load_basket_data() -> pd.DataFrame:
    """Load basket/receipt line data for co-purchase analysis."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_basket_analysis`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Basket query failed, using demo data: {e}")
    return _generate_demo_basket_data()


@st.cache_data(ttl=300)
def load_budget_data() -> pd.DataFrame:
    """Load budget data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_budget`
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Budget query failed, using demo data: {e}")
    return _generate_demo_budget_data()


@st.cache_data(ttl=300)
def load_daily_sales() -> pd.DataFrame:
    """Load daily sales data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_sales_daily`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Daily sales query failed, using demo data: {e}")
    return _generate_demo_daily_sales()


@st.cache_data(ttl=300)
def load_discount_detail() -> pd.DataFrame:
    """Load discount detail data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_discount_detail`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Discount detail query failed, using demo data: {e}")
    return _generate_demo_discount_detail()


@st.cache_data(ttl=300)
def load_waste_data() -> pd.DataFrame:
    """Load waste/loss data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_waste_loss`
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Waste query failed, using demo data: {e}")
    return _generate_demo_waste_data()


def _generate_demo_budget_pl() -> pd.DataFrame:
    """Generate demo store-level P&L budget data."""
    np.random.seed(1300)
    stores = [
        ("S001", "バンコク中央店"),
        ("S002", "チェンマイ店"),
        ("S003", "パタヤ店"),
        ("S004", "プーケット店"),
    ]
    yms = _generate_demo_dates(24)

    rows = []
    for ym in yms:
        month = int(ym[5:7])
        seasonal = 1.0 + 0.08 * np.sin(month * np.pi / 6)
        for store_id, store_name in stores:
            size_factor = {"S001": 1.5, "S002": 0.8, "S003": 1.0, "S004": 0.7}[store_id]
            # Budget is slightly above or below actual for realism
            net_sales = round(np.random.uniform(8_500_000, 14_500_000) * size_factor * seasonal, 2)
            cogs_rate = np.random.uniform(0.66, 0.73)
            cogs = round(net_sales * cogs_rate, 2)
            gross_profit = round(net_sales - cogs, 2)
            personnel = round(net_sales * np.random.uniform(0.08, 0.11), 2)
            rent = round(np.random.uniform(210_000, 580_000) * size_factor, 2)
            utility = round(np.random.uniform(85_000, 190_000) * size_factor, 2)
            depreciation = round(np.random.uniform(55_000, 140_000) * size_factor, 2)
            other = round(net_sales * np.random.uniform(0.02, 0.035), 2)
            total_opex = personnel + rent + utility + depreciation + other
            op_profit = round(gross_profit - total_opex, 2)
            ns = net_sales
            rows.append({
                "ym": ym, "store_id": store_id, "store_name": store_name,
                "net_sales": ns, "cogs": cogs,
                "gross_profit": gross_profit,
                "gross_margin_pct": round(gross_profit / ns * 100, 1) if ns else 0,
                "personnel_expense": personnel, "rent_expense": rent,
                "utility_expense": utility, "depreciation_expense": depreciation,
                "other_opex": other, "total_opex": round(total_opex, 2),
                "operating_profit": op_profit,
                "operating_margin_pct": round(op_profit / ns * 100, 1) if ns else 0,
                "personnel_ratio_pct": round(personnel / ns * 100, 1),
                "rent_ratio_pct": round(rent / ns * 100, 1),
                "utility_ratio_pct": round(utility / ns * 100, 1),
                "depreciation_ratio_pct": round(depreciation / ns * 100, 1),
                "other_opex_ratio_pct": round(other / ns * 100, 1),
                "total_opex_ratio_pct": round(total_opex / ns * 100, 1),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_budget_pl() -> pd.DataFrame:
    """Load store-level P&L budget data."""
    config = get_config()
    client = _get_bq_client()
    if client is not None:
        query = f"""
            SELECT * FROM `{config.gcp_project_id}.{config.bq_dataset_mart}.v_budget_pl_monthly`
            ORDER BY ym DESC, store_id
        """
        try:
            df = client.query(query).to_dataframe()
            if len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f"Budget PL query failed, using demo data: {e}")
    return _generate_demo_budget_pl()


def get_store_list() -> list[tuple[str, str]]:
    """Get list of (store_id, store_name) pairs."""
    df = load_sales_monthly()
    if len(df) > 0 and "store_id" in df.columns:
        stores = df[["store_id", "store_name"]].drop_duplicates()
        return [(r.store_id, r.store_name) for _, r in stores.iterrows()]
    return [
        ("S001", "バンコク中央店"),
        ("S002", "チェンマイ店"),
        ("S003", "パタヤ店"),
        ("S004", "プーケット店"),
    ]


def get_department_list() -> list[tuple[str, str]]:
    """Get list of (dept_id, dept_name) pairs."""
    df = load_sales_monthly()
    if len(df) > 0 and "dept_id" in df.columns:
        depts = df[["dept_id", "dept_name"]].drop_duplicates()
        return [(r.dept_id, r.dept_name) for _, r in depts.iterrows()]
    config = get_config()
    return [(d["id"], d["name"]) for d in config.departments]


def get_ym_list() -> list[str]:
    """Get list of available year-months."""
    df = load_sales_monthly()
    if len(df) > 0 and "ym" in df.columns:
        return sorted(df["ym"].unique().tolist(), reverse=True)
    return _generate_demo_dates(24)[::-1]
