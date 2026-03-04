"""
Unit tests for data access layer (demo data generation).
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data import (
    _generate_demo_category_data,
    _generate_demo_forecast,
    _generate_demo_oos_data,
    _generate_demo_sales_monthly,
)


class TestDemoDataGeneration:
    """Tests for demo data generators."""

    def test_sales_monthly_shape(self) -> None:
        df = _generate_demo_sales_monthly()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        required_cols = [
            "ym", "store_id", "store_name", "dept_id", "dept_name",
            "gross_sales_ex_tax", "net_sales_ex_tax", "gross_profit",
            "gross_margin_pct",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_sales_monthly_has_multiple_stores(self) -> None:
        df = _generate_demo_sales_monthly()
        assert df["store_id"].nunique() >= 2

    def test_sales_monthly_has_all_departments(self) -> None:
        df = _generate_demo_sales_monthly()
        assert df["dept_id"].nunique() >= 5

    def test_sales_monthly_values_positive(self) -> None:
        df = _generate_demo_sales_monthly()
        assert (df["gross_sales_ex_tax"] >= 0).all()
        assert (df["net_sales_ex_tax"] >= 0).all()

    def test_sales_monthly_gross_gte_net(self) -> None:
        df = _generate_demo_sales_monthly()
        assert (df["gross_sales_ex_tax"] >= df["net_sales_ex_tax"]).all()

    def test_category_data_shape(self) -> None:
        df = _generate_demo_category_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "cat_l" in df.columns
        assert "cat_m" in df.columns
        assert "cat_s" in df.columns

    def test_oos_data_shape(self) -> None:
        df = _generate_demo_oos_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "is_oos_suspect" in df.columns
        assert "opportunity_loss_amount" in df.columns

    def test_oos_data_has_suspects(self) -> None:
        df = _generate_demo_oos_data()
        assert df["is_oos_suspect"].sum() > 0

    def test_forecast_data_shape(self) -> None:
        df = _generate_demo_forecast()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "forecast_sales" in df.columns
        assert "elapsed_days" in df.columns
        assert "total_days" in df.columns

    def test_composition_percentages(self) -> None:
        df = _generate_demo_sales_monthly()
        # Check composition sums to ~100% per store per month
        for (ym, store_id), group in df.groupby(["ym", "store_id"]):
            total_comp = group["sales_composition_pct"].sum()
            assert abs(total_comp - 100) < 1.0, (
                f"Sales composition for {ym}/{store_id} = {total_comp}%"
            )
