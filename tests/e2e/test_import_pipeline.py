"""
E2E test for the import pipeline (without BigQuery).
Tests the full flow: file read → validate → process → audit record.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from etl.importer import (
    create_audit_record,
    process_import,
)


class TestImportPipelineE2E:
    """End-to-end tests for import pipeline."""

    def _make_csv(self, data: dict) -> bytes:
        df = pd.DataFrame(data)
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        return buf.getvalue()

    def test_full_sales_item_flow(self) -> None:
        """Test complete flow for sales_item_daily import."""
        csv = self._make_csv({
            "日付": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "店舗コード": ["S001", "S001", "S002"],
            "商品コード": ["SKU001", "SKU002", "SKU001"],
            "粗売上金額": [10000, 20000, 15000],
            "売上点数": [5, 10, 7],
            "部門": ["食品", "青果", "食品"],
        })

        result = process_import(
            file_content=csv,
            filename="sales_test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        assert result["status"] == "success"
        assert result["row_count"] == 3
        assert result["file_checksum"] is not None
        assert result["dry_run"] is True

        preview = result["preview"]
        assert len(preview) == 3
        assert "date" in preview.columns
        assert "store_id" in preview.columns

    def test_full_settlement_flow(self) -> None:
        """Test complete flow for settlement data import."""
        csv = self._make_csv({
            "日付": ["2024-01-01", "2024-01-01"],
            "店舗コード": ["S001", "S001"],
            "レシートNo": ["R001", "R002"],
            "決済方法": ["現金", "カード"],
            "金額": [5000, -1000],
            "返品フラグ": ["0", "1"],
        })

        result = process_import(
            file_content=csv,
            filename="settlement_test.csv",
            source_type="settlement",
            imported_by="test_user",
            dry_run=True,
        )

        assert result["status"] == "success"
        assert result["row_count"] == 2

    def test_full_master_store_flow(self) -> None:
        """Test complete flow for store master import."""
        csv = self._make_csv({
            "店舗コード": ["S001", "S002"],
            "店舗名": ["バンコク中央店", "チェンマイ店"],
            "地域": ["バンコク", "チェンマイ"],
        })

        result = process_import(
            file_content=csv,
            filename="master_store.csv",
            source_type="master_store",
            imported_by="test_user",
            dry_run=True,
        )

        assert result["status"] == "success"
        assert result["row_count"] == 2

    def test_audit_record_creation(self) -> None:
        """Test audit record is properly created."""
        csv = self._make_csv({
            "日付": ["2024-01-01"],
            "店舗コード": ["S001"],
            "商品コード": ["SKU001"],
            "粗売上金額": [10000],
            "売上点数": [5],
        })

        result = process_import(
            file_content=csv,
            filename="audit_test.csv",
            source_type="sales_item_daily",
            imported_by="audit_user",
            dry_run=True,
        )

        audit = create_audit_record(result, "sales_item_daily", "audit_test.csv", "audit_user")

        assert audit["import_id"] == result["import_id"]
        assert audit["source_type"] == "sales_item_daily"
        assert audit["source_file"] == "audit_test.csv"
        assert audit["imported_by"] == "audit_user"
        assert audit["status"] == "success"
        assert audit["row_count"] == 1

    def test_mixed_valid_invalid_rows(self) -> None:
        """Test handling of mixed valid and invalid data."""
        csv = self._make_csv({
            "日付": ["2024-01-01", "invalid-date", "2024-01-03"],
            "店舗コード": ["S001", "S001", "S002"],
            "商品コード": ["SKU001", "SKU002", "SKU003"],
            "粗売上金額": [10000, "not-a-number", 15000],
            "売上点数": [5, 10, 7],
        })

        result = process_import(
            file_content=csv,
            filename="mixed_test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        # Should be partial (some errors, some valid)
        assert result["status"] in ("success", "partial")
        assert result["row_count"] >= 1  # At least some valid rows

    def test_completely_empty_file(self) -> None:
        """Test handling of empty file."""
        csv = "日付,店舗コード,商品コード,粗売上金額,売上点数\n".encode("utf-8")

        result = process_import(
            file_content=csv,
            filename="empty_test.csv",
            source_type="sales_item_daily",
            imported_by="test_user",
            dry_run=True,
        )

        assert result["row_count"] == 0

    def test_idempotency_same_file(self) -> None:
        """Test that the same file produces the same checksum."""
        csv = self._make_csv({
            "日付": ["2024-01-01"],
            "店舗コード": ["S001"],
            "商品コード": ["SKU001"],
            "粗売上金額": [10000],
            "売上点数": [5],
        })

        r1 = process_import(
            file_content=csv, filename="test.csv",
            source_type="sales_item_daily", imported_by="user1", dry_run=True,
        )
        r2 = process_import(
            file_content=csv, filename="test.csv",
            source_type="sales_item_daily", imported_by="user2", dry_run=True,
        )

        assert r1["file_checksum"] == r2["file_checksum"]
