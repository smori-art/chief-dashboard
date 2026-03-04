"""
Unit tests for ETL importer module.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from etl.importer import (
    apply_type_conversions,
    compute_file_checksum,
    load_column_mappings,
    map_department_names,
    process_import,
    resolve_columns,
    validate_dataframe,
)


class TestComputeChecksum:
    """Tests for file checksum computation."""

    def test_same_content_same_checksum(self) -> None:
        content = b"test data content"
        assert compute_file_checksum(content) == compute_file_checksum(content)

    def test_different_content_different_checksum(self) -> None:
        assert compute_file_checksum(b"data1") != compute_file_checksum(b"data2")

    def test_returns_hex_string(self) -> None:
        result = compute_file_checksum(b"test")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex length


class TestLoadColumnMappings:
    """Tests for column mapping YAML loading."""

    def test_loads_mappings(self) -> None:
        mappings = load_column_mappings()
        assert isinstance(mappings, dict)
        assert "sales_item_daily" in mappings
        assert "sales_store_daily" in mappings
        assert "receipt_line" in mappings
        assert "settlement" in mappings
        assert "master_store" in mappings
        assert "master_product" in mappings

    def test_mapping_has_required_fields(self) -> None:
        mappings = load_column_mappings()
        for source_type, config in mappings.items():
            assert "target_table" in config, f"{source_type} missing target_table"
            assert "columns" in config, f"{source_type} missing columns"
            assert "required" in config, f"{source_type} missing required"


class TestResolveColumns:
    """Tests for column name resolution."""

    def test_resolves_japanese_columns(self) -> None:
        df = pd.DataFrame({
            "日付": ["2024-01-01"],
            "店舗コード": ["S001"],
            "商品コード": ["SKU001"],
            "粗売上金額": [10000],
            "売上点数": [5],
        })
        mappings = load_column_mappings()
        column_mapping = mappings["sales_item_daily"]["columns"]

        df_resolved, resolved = resolve_columns(df, column_mapping)

        assert "date" in df_resolved.columns
        assert "store_id" in df_resolved.columns
        assert "sku" in df_resolved.columns
        assert "gross_sales_ex_tax" in df_resolved.columns

    def test_resolves_english_columns(self) -> None:
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "store_id": ["S001"],
            "sku": ["SKU001"],
            "gross_sales": [10000],
            "qty": [5],
        })
        mappings = load_column_mappings()
        column_mapping = mappings["sales_item_daily"]["columns"]

        df_resolved, resolved = resolve_columns(df, column_mapping)

        assert "date" in df_resolved.columns
        assert "store_id" in df_resolved.columns


class TestValidateDataframe:
    """Tests for DataFrame validation."""

    def test_valid_data_passes(self) -> None:
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "store_id": ["S001"],
            "sku": ["SKU001"],
            "gross_sales_ex_tax": [10000],
        })
        config = {
            "required": ["date", "store_id", "sku", "gross_sales_ex_tax"],
            "date_columns": ["date"],
            "numeric_columns": ["gross_sales_ex_tax"],
        }

        valid_df, errors = validate_dataframe(df, config)
        assert len(valid_df) == 1
        error_count = len([e for e in errors if e.get("severity") == "error"])
        assert error_count == 0

    def test_missing_required_column_fails(self) -> None:
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "store_id": ["S001"],
        })
        config = {
            "required": ["date", "store_id", "sku", "gross_sales_ex_tax"],
            "date_columns": ["date"],
            "numeric_columns": [],
        }

        valid_df, errors = validate_dataframe(df, config)
        fatal = [e for e in errors if e.get("severity") == "fatal"]
        assert len(fatal) > 0

    def test_null_required_field_errors(self) -> None:
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "store_id": [None],
            "sku": ["SKU001"],
            "gross_sales_ex_tax": [10000],
        })
        config = {
            "required": ["date", "store_id", "sku", "gross_sales_ex_tax"],
            "date_columns": ["date"],
            "numeric_columns": ["gross_sales_ex_tax"],
        }

        valid_df, errors = validate_dataframe(df, config)
        assert len(valid_df) == 0
        assert len(errors) > 0


class TestMapDepartmentNames:
    """Tests for department name to ID mapping."""

    def test_maps_japanese_names(self) -> None:
        df = pd.DataFrame({"dept_name": ["食品", "青果", "鮮魚", "精肉", "惣菜"]})
        result = map_department_names(df)
        assert result["dept_id"].tolist() == [
            "food", "produce", "seafood", "meat", "deli"
        ]

    def test_maps_english_names(self) -> None:
        df = pd.DataFrame({"dept_name": ["food", "produce"]})
        result = map_department_names(df)
        assert result["dept_id"].tolist() == ["food", "produce"]

    def test_handles_missing_column(self) -> None:
        df = pd.DataFrame({"other_col": ["value"]})
        result = map_department_names(df)
        assert "dept_id" not in result.columns


class TestProcessImport:
    """Tests for the full import process."""

    def _create_test_csv(self, data: dict) -> bytes:
        """Create test CSV file content."""
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue()

    def test_valid_sales_item_daily(self) -> None:
        csv_data = self._create_test_csv({
            "日付": ["2024-01-01", "2024-01-02"],
            "店舗コード": ["S001", "S001"],
            "商品コード": ["SKU001", "SKU002"],
            "粗売上金額": [10000, 20000],
            "売上点数": [5, 10],
        })

        result = process_import(
            file_content=csv_data,
            filename="test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        assert result["status"] in ("success", "partial")
        assert result["row_count"] == 2

    def test_invalid_source_type(self) -> None:
        result = process_import(
            file_content=b"test",
            filename="test.csv",
            source_type="nonexistent",
            imported_by="test_user",
            dry_run=True,
        )
        assert result["status"] == "fail"

    def test_idempotency_checksum(self) -> None:
        csv_data = self._create_test_csv({
            "日付": ["2024-01-01"],
            "店舗コード": ["S001"],
            "商品コード": ["SKU001"],
            "粗売上金額": [10000],
            "売上点数": [5],
        })

        result1 = process_import(
            file_content=csv_data,
            filename="test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        result2 = process_import(
            file_content=csv_data,
            filename="test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        # Same file should produce same checksum
        assert result1["file_checksum"] == result2["file_checksum"]
