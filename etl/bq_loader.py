"""
BigQuery Loader: Handles loading validated DataFrames into BigQuery.

Features:
- Idempotent loading (checksum-based dedup)
- Raw → Staging promotion
- Audit log writing
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
from loguru import logger

try:
    from google.cloud import bigquery
    from google.cloud.bigquery import LoadJobConfig, WriteDisposition

    HAS_BQ = True
except ImportError:
    HAS_BQ = False
    logger.warning("google-cloud-bigquery not installed. Using mock mode.")


def get_bq_client() -> Any:
    """Get BigQuery client."""
    if not HAS_BQ:
        return None
    project_id = os.getenv("GCP_PROJECT_ID")
    return bigquery.Client(project=project_id)


def get_dataset_ref(dataset_name: str) -> str:
    """Get full dataset reference."""
    project_id = os.getenv("GCP_PROJECT_ID", "")
    return f"{project_id}.{dataset_name}"


def check_checksum_exists(
    client: Any,
    dataset_raw: str,
    table_name: str,
    file_checksum: str,
) -> bool:
    """
    Check if a file with the same checksum has already been imported.
    Returns True if duplicate (already imported).
    """
    if client is None:
        return False

    project_id = os.getenv("GCP_PROJECT_ID", "")
    query = f"""
        SELECT COUNT(*) as cnt
        FROM `{project_id}.{dataset_raw}.import_audit_log`
        WHERE file_checksum = @checksum
        AND status IN ('success', 'partial')
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("checksum", "STRING", file_checksum),
        ]
    )
    try:
        result = client.query(query, job_config=job_config).result()
        for row in result:
            return row.cnt > 0
    except Exception as e:
        logger.warning(f"Checksum check failed (table may not exist yet): {e}")
    return False


def load_to_raw(
    client: Any,
    df: pd.DataFrame,
    dataset_raw: str,
    table_name: str,
) -> int:
    """
    Load DataFrame to raw table in BigQuery.
    Returns number of rows loaded.
    """
    if client is None:
        logger.info(f"[Mock] Would load {len(df)} rows to {dataset_raw}.{table_name}")
        return len(df)

    project_id = os.getenv("GCP_PROJECT_ID", "")
    table_ref = f"{project_id}.{dataset_raw}.{table_name}"

    job_config = LoadJobConfig(
        write_disposition=WriteDisposition.WRITE_APPEND,
    )

    try:
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()
        logger.info(f"Loaded {job.output_rows} rows to {table_ref}")
        return job.output_rows
    except Exception as e:
        logger.error(f"Failed to load to {table_ref}: {e}")
        raise


def write_audit_log(
    client: Any,
    dataset_raw: str,
    audit_record: dict[str, Any],
) -> None:
    """Write audit log record to BigQuery."""
    if client is None:
        logger.info(f"[Mock] Audit log: {audit_record}")
        return

    project_id = os.getenv("GCP_PROJECT_ID", "")
    table_ref = f"{project_id}.{dataset_raw}.import_audit_log"
    df = pd.DataFrame([audit_record])

    job_config = LoadJobConfig(
        write_disposition=WriteDisposition.WRITE_APPEND,
    )

    try:
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()
        logger.info(f"Audit log written for import {audit_record['import_id']}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def promote_raw_to_stg(
    client: Any,
    dataset_raw: str,
    dataset_stg: str,
    raw_table: str,
    stg_table: str,
    file_checksum: str,
) -> int:
    """
    Promote data from raw to staging (deduplicated).
    Uses MERGE to avoid duplicates based on natural key.
    Returns rows affected.
    """
    if client is None:
        logger.info(f"[Mock] Would promote {raw_table} -> {stg_table}")
        return 0

    project_id = os.getenv("GCP_PROJECT_ID", "")

    # Build merge key based on table type
    merge_keys = _get_merge_keys(stg_table)
    if not merge_keys:
        logger.warning(f"No merge keys defined for {stg_table}, skipping promotion")
        return 0

    merge_on = " AND ".join([f"t.{k} = s.{k}" for k in merge_keys])

    # Get column list from raw table (excluding audit columns for stg)
    raw_ref = f"{project_id}.{dataset_raw}.{raw_table}"
    stg_ref = f"{project_id}.{dataset_stg}.{stg_table}"

    query = f"""
        MERGE `{stg_ref}` AS t
        USING (
            SELECT * FROM `{raw_ref}`
            WHERE _file_checksum = @checksum
        ) AS s
        ON {merge_on}
        WHEN NOT MATCHED THEN
            INSERT ROW
        WHEN MATCHED THEN
            UPDATE SET _imported_at = s._imported_at, _source_file = s._source_file
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("checksum", "STRING", file_checksum),
        ]
    )

    try:
        result = client.query(query, job_config=job_config).result()
        rows = result.num_dml_affected_rows if hasattr(result, "num_dml_affected_rows") else 0
        logger.info(f"Promoted {rows} rows from {raw_table} to {stg_table}")
        return rows
    except Exception as e:
        logger.error(f"Promotion failed for {stg_table}: {e}")
        raise


def _get_merge_keys(stg_table: str) -> list[str]:
    """Get natural key columns for each staging table."""
    keys_map: dict[str, list[str]] = {
        "f_sales_item_daily": ["date", "store_id", "sku"],
        "f_sales_store_daily": ["date", "store_id"],
        "f_receipt_line": ["date", "store_id", "receipt_id", "line_no"],
        "f_settlement": ["date", "store_id", "receipt_id", "tender_type"],
        "f_sales_dept_timeband_daily": ["date", "store_id", "dept_id", "timeband_id"],
        "f_inventory_monthly": ["month_end_date", "store_id", "sku"],
        "f_waste_discount_daily": ["date", "store_id", "sku"],
        "dim_store": ["store_id"],
        "dim_product": ["sku"],
    }
    return keys_map.get(stg_table, [])


def full_import_pipeline(
    file_content: bytes,
    filename: str,
    source_type: str,
    imported_by: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Execute the full import pipeline:
    1. Parse & validate
    2. Check idempotency (checksum)
    3. Load to raw
    4. Write audit log
    5. Promote to staging

    Returns import result dict.
    """
    from etl.importer import (
        create_audit_record,
        load_column_mappings,
        process_import,
    )

    dataset_raw = os.getenv("BQ_DATASET_RAW", "chief_raw")
    dataset_stg = os.getenv("BQ_DATASET_STG", "chief_stg")

    # Step 1: Process (parse, validate)
    mappings = load_column_mappings()
    result = process_import(
        file_content=file_content,
        filename=filename,
        source_type=source_type,
        imported_by=imported_by,
        mappings=mappings,
        dry_run=dry_run,
    )

    if result["status"] == "fail" or dry_run:
        return result

    # Step 2: Check idempotency
    client = get_bq_client()
    file_checksum = result.get("file_checksum", "")

    if check_checksum_exists(client, dataset_raw, result["target_table"], file_checksum):
        result["status"] = "skipped"
        result["error_message"] = "同一ファイルは既にインポート済みです（チェックサム一致）"
        logger.warning(f"Duplicate file detected: {filename} (checksum: {file_checksum})")
        return result

    # Step 3: Load to raw
    df = result.get("dataframe")
    if df is not None and len(df) > 0:
        try:
            rows_loaded = load_to_raw(client, df, dataset_raw, result["target_table"])
            result["rows_loaded_raw"] = rows_loaded
        except Exception as e:
            result["status"] = "fail"
            result["error_message"] = f"BigQueryロード失敗: {e}"
            return result

    # Step 4: Audit log
    audit_record = create_audit_record(result, source_type, filename, imported_by)
    write_audit_log(client, dataset_raw, audit_record)
    result["audit_record"] = audit_record

    # Step 5: Promote to staging
    stg_table = result.get("stg_table")
    if stg_table:
        try:
            rows_promoted = promote_raw_to_stg(
                client, dataset_raw, dataset_stg,
                result["target_table"], stg_table, file_checksum,
            )
            result["rows_promoted_stg"] = rows_promoted
        except Exception as e:
            logger.error(f"Staging promotion failed: {e}")
            result["stg_promotion_error"] = str(e)

    return result
