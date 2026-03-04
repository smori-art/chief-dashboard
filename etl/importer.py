"""
Excel → BigQuery Importer with validation, idempotency, and audit logging.

Supports:
- Column name fuzzy matching via YAML mappings
- SHA256 checksum for deduplication
- Row-level validation with error reporting
- Audit trail for every import
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from loguru import logger

# Type alias for import results
ImportResult = dict[str, Any]

# Department name -> ID mapping (Japanese/Thai to internal ID)
DEPT_NAME_MAP: dict[str, str] = {
    "食品": "food",
    "青果": "produce",
    "鮮魚": "seafood",
    "精肉": "meat",
    "惣菜": "deli",
    "店舗管理": "store_mgmt",
    # Allow English names too
    "food": "food",
    "produce": "produce",
    "seafood": "seafood",
    "meat": "meat",
    "deli": "deli",
    "store_mgmt": "store_mgmt",
}


def load_column_mappings(mappings_path: str | None = None) -> dict[str, Any]:
    """Load column mapping definitions from YAML."""
    if mappings_path is None:
        mappings_path = str(Path(__file__).parent / "column_mappings.yaml")
    with open(mappings_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_file_checksum(file_content: bytes) -> str:
    """Compute SHA256 checksum of file content."""
    return hashlib.sha256(file_content).hexdigest()


def resolve_columns(
    df: pd.DataFrame,
    column_mapping: dict[str, list[str]],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Match DataFrame columns to target schema using the mapping definitions.

    Returns:
        Tuple of (renamed DataFrame, mapping used: {target_col: source_col})
    """
    resolved: dict[str, str] = {}
    source_cols = set(df.columns)

    for target_col, possible_names in column_mapping.items():
        for name in possible_names:
            if name in source_cols:
                resolved[target_col] = name
                break

    # Rename matched columns
    rename_map = {v: k for k, v in resolved.items()}
    df_renamed = df.rename(columns=rename_map)

    return df_renamed, resolved


def validate_dataframe(
    df: pd.DataFrame,
    source_type_config: dict[str, Any],
    existing_store_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """
    Validate a DataFrame against schema rules.

    Returns:
        Tuple of (valid rows DataFrame, list of error dicts)
    """
    errors: list[dict[str, Any]] = []
    required_cols = source_type_config.get("required", [])
    date_cols = source_type_config.get("date_columns", [])
    numeric_cols = source_type_config.get("numeric_columns", [])

    # Check required columns exist
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append({
            "row": 0,
            "column": ",".join(missing_cols),
            "error": f"必須列が見つかりません: {missing_cols}",
            "severity": "fatal",
        })
        return df.head(0), errors

    # Row-level validation
    error_rows: set[int] = set()

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # Excel row number (1-indexed + header)

        # Required field check
        for col in required_cols:
            if col in df.columns and pd.isna(row.get(col)):
                errors.append({
                    "row": row_num,
                    "column": col,
                    "error": f"必須項目が空です",
                    "severity": "error",
                })
                error_rows.add(int(idx))

        # Date validation
        for col in date_cols:
            if col in df.columns and not pd.isna(row.get(col)):
                try:
                    pd.to_datetime(row[col])
                except (ValueError, TypeError):
                    errors.append({
                        "row": row_num,
                        "column": col,
                        "error": f"日付形式が不正: {row[col]}",
                        "severity": "error",
                    })
                    error_rows.add(int(idx))

        # Numeric validation
        for col in numeric_cols:
            if col in df.columns and not pd.isna(row.get(col)):
                try:
                    float(row[col])
                except (ValueError, TypeError):
                    errors.append({
                        "row": row_num,
                        "column": col,
                        "error": f"数値形式が不正: {row[col]}",
                        "severity": "error",
                    })
                    error_rows.add(int(idx))

        # Store ID existence check
        if existing_store_ids and "store_id" in df.columns:
            store_val = row.get("store_id")
            if not pd.isna(store_val) and str(store_val) not in existing_store_ids:
                errors.append({
                    "row": row_num,
                    "column": "store_id",
                    "error": f"未登録の店舗ID: {store_val}",
                    "severity": "warning",
                })

    # Return valid rows (excluding error rows)
    valid_df = df.drop(index=list(error_rows))
    return valid_df, errors


def apply_type_conversions(
    df: pd.DataFrame,
    source_type_config: dict[str, Any],
) -> pd.DataFrame:
    """Apply type conversions for date and numeric columns."""
    df = df.copy()
    date_cols = source_type_config.get("date_columns", [])
    numeric_cols = source_type_config.get("numeric_columns", [])

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def map_department_names(df: pd.DataFrame) -> pd.DataFrame:
    """Convert department names to department IDs."""
    df = df.copy()
    if "dept_name" in df.columns:
        df["dept_id"] = df["dept_name"].map(
            lambda x: DEPT_NAME_MAP.get(str(x).strip(), str(x).strip().lower())
            if pd.notna(x) else None
        )
    return df


def add_audit_columns(
    df: pd.DataFrame,
    source_file: str,
    file_checksum: str,
    imported_by: str,
) -> pd.DataFrame:
    """Add audit columns to the DataFrame."""
    df = df.copy()
    df["_source_file"] = source_file
    df["_imported_at"] = datetime.now(timezone.utc)
    df["_imported_by"] = imported_by
    df["_file_checksum"] = file_checksum
    df["_row_number"] = range(1, len(df) + 1)
    return df


def read_excel_file(
    file_content: bytes,
    filename: str,
) -> pd.DataFrame:
    """Read Excel or CSV file content into DataFrame."""
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(io.BytesIO(file_content))
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(io.BytesIO(file_content))
    else:
        raise ValueError(f"未対応のファイル形式: {ext}")


def process_import(
    file_content: bytes,
    filename: str,
    source_type: str,
    imported_by: str,
    mappings: dict[str, Any] | None = None,
    existing_store_ids: set[str] | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """
    Process a single file import.

    Args:
        file_content: Raw file bytes
        filename: Original filename
        source_type: Source type key (e.g., 'sales_item_daily')
        imported_by: Username of importer
        mappings: Column mappings (loaded from YAML if None)
        existing_store_ids: Set of valid store IDs for validation
        dry_run: If True, validate only without loading

    Returns:
        ImportResult dict with status, errors, preview, etc.
    """
    import_id = str(uuid.uuid4())
    file_checksum = compute_file_checksum(file_content)

    if mappings is None:
        mappings = load_column_mappings()

    if source_type not in mappings:
        return {
            "import_id": import_id,
            "status": "fail",
            "error_message": f"未知のデータ種別: {source_type}",
            "errors": [],
            "row_count": 0,
        }

    source_config = mappings[source_type]
    column_mapping = source_config["columns"]
    target_table = source_config["target_table"]

    try:
        # Step 1: Read file
        logger.info(f"Reading file: {filename}")
        df_raw = read_excel_file(file_content, filename)
        logger.info(f"Read {len(df_raw)} rows from {filename}")

        # Step 2: Resolve columns
        df_resolved, resolved_mapping = resolve_columns(df_raw, column_mapping)
        logger.info(f"Column mapping: {resolved_mapping}")

        # Step 3: Validate
        df_valid, errors = validate_dataframe(
            df_resolved, source_config, existing_store_ids
        )

        fatal_errors = [e for e in errors if e.get("severity") == "fatal"]
        if fatal_errors:
            return {
                "import_id": import_id,
                "status": "fail",
                "error_message": "必須列が不足しています",
                "errors": errors,
                "row_count": 0,
                "target_table": target_table,
                "column_mapping_used": resolved_mapping,
            }

        # Step 4: Type conversions
        df_typed = apply_type_conversions(df_valid, source_config)

        # Step 5: Map department names to IDs
        df_typed = map_department_names(df_typed)

        # Step 6: Add audit columns
        df_final = add_audit_columns(df_typed, filename, file_checksum, imported_by)

        # Keep only mapped columns + audit columns
        target_cols = list(column_mapping.keys())
        if "dept_id" in df_final.columns:
            target_cols.append("dept_id")
        audit_cols = [
            "_source_file", "_imported_at", "_imported_by",
            "_file_checksum", "_row_number",
        ]
        keep_cols = [c for c in target_cols + audit_cols if c in df_final.columns]
        df_final = df_final[keep_cols]

        result: ImportResult = {
            "import_id": import_id,
            "status": "success" if not errors else "partial",
            "error_message": None if not errors else f"{len(errors)}件のエラー（エラー行をスキップ）",
            "errors": errors,
            "row_count": len(df_final),
            "total_rows_in_file": len(df_raw),
            "skipped_rows": len(df_raw) - len(df_final),
            "target_table": target_table,
            "stg_table": source_config.get("stg_table"),
            "file_checksum": file_checksum,
            "column_mapping_used": resolved_mapping,
            "preview": df_final.head(20),
            "dataframe": df_final if not dry_run else None,
            "dry_run": dry_run,
        }

        return result

    except Exception as e:
        logger.exception(f"Import failed for {filename}")
        return {
            "import_id": import_id,
            "status": "fail",
            "error_message": str(e),
            "errors": [{"row": 0, "column": "", "error": str(e), "severity": "fatal"}],
            "row_count": 0,
            "target_table": target_table,
        }


def create_audit_record(
    import_result: ImportResult,
    source_type: str,
    filename: str,
    imported_by: str,
) -> dict[str, Any]:
    """Create an audit log record from import result."""
    return {
        "import_id": import_result["import_id"],
        "source_type": source_type,
        "source_file": filename,
        "file_checksum": import_result.get("file_checksum", ""),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "imported_by": imported_by,
        "row_count": import_result.get("row_count", 0),
        "status": import_result["status"],
        "error_message": import_result.get("error_message"),
        "error_rows": json.dumps(
            import_result.get("errors", [])[:100],  # Limit stored errors
            ensure_ascii=False,
        ),
    }
