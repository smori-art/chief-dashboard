-- ============================================================
-- Chief Dashboard - RAW Layer DDL
-- Dataset: chief_raw
-- Purpose: Store imported data in original form with audit columns
-- ============================================================

-- Raw: Daily item-level sales (source type 1)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_sales_item_daily` (
    date DATE,
    store_id STRING,
    sku STRING,
    product_name STRING,
    dept_name STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    gross_sales_ex_tax NUMERIC,
    qty NUMERIC,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
PARTITION BY date
CLUSTER BY store_id, sku
OPTIONS (
    description = 'Raw daily item-level sales from Excel import'
);

-- Raw: Daily store-level sales (source type 2/6)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_sales_store_daily` (
    date DATE,
    store_id STRING,
    store_name STRING,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    receipts INT64,
    qty NUMERIC,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
PARTITION BY date
CLUSTER BY store_id
OPTIONS (
    description = 'Raw daily store-level sales from Excel import'
);

-- Raw: Receipt line detail (source type 3)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_receipt_line` (
    date DATE,
    store_id STRING,
    receipt_id STRING,
    line_no INT64,
    sku STRING,
    product_name STRING,
    qty NUMERIC,
    unit_price_ex_tax NUMERIC,
    gross_amount_ex_tax NUMERIC,
    discount_amount_ex_tax NUMERIC,
    net_amount_ex_tax NUMERIC,
    time STRING,
    dept_name STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
PARTITION BY date
CLUSTER BY store_id, receipt_id
OPTIONS (
    description = 'Raw receipt line detail from Excel import'
);

-- Raw: Settlement data (source type 4)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_settlement` (
    date DATE,
    store_id STRING,
    receipt_id STRING,
    tender_type STRING,
    amount NUMERIC,
    is_refund_flag STRING,
    refund_reason_code STRING,
    original_receipt_id STRING,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
PARTITION BY date
CLUSTER BY store_id
OPTIONS (
    description = 'Raw settlement data from Excel import'
);

-- Raw: Daily department x timeband sales (source type 5)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_sales_dept_timeband` (
    date DATE,
    store_id STRING,
    dept_name STRING,
    time_start STRING,
    time_end STRING,
    timeband_label STRING,
    gross_sales_ex_tax NUMERIC,
    qty NUMERIC,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
PARTITION BY date
CLUSTER BY store_id, dept_name
OPTIONS (
    description = 'Raw daily department x timeband sales from Excel import'
);

-- Raw: Master - Stores
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_master_store` (
    store_id STRING,
    store_name STRING,
    open_date STRING,
    region STRING,
    timezone STRING,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
);

-- Raw: Master - Products
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_master_product` (
    sku STRING,
    product_name STRING,
    dept_name STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    uom STRING,
    standard_cost NUMERIC,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
);

-- Raw: Store P&L Monthly (source type 8)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.raw_store_pl_monthly` (
    ym STRING,
    store_id STRING,
    store_name STRING,
    net_sales NUMERIC,
    cogs NUMERIC,
    gross_profit NUMERIC,
    personnel_expense NUMERIC,
    rent_expense NUMERIC,
    utility_expense NUMERIC,
    depreciation_expense NUMERIC,
    other_opex NUMERIC,
    operating_profit NUMERIC,
    -- Audit columns
    _source_file STRING NOT NULL,
    _imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _imported_by STRING NOT NULL,
    _file_checksum STRING NOT NULL,
    _row_number INT64
)
OPTIONS (
    description = 'Raw monthly store-level P&L from Excel import'
);

-- Import Audit Log
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_RAW}.import_audit_log` (
    import_id STRING NOT NULL,
    source_type STRING NOT NULL,
    source_file STRING NOT NULL,
    file_checksum STRING NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    imported_by STRING NOT NULL,
    row_count INT64,
    status STRING NOT NULL,  -- success / fail / partial
    error_message STRING,
    error_rows STRING  -- JSON array of error details
)
OPTIONS (
    description = 'Audit log for all data imports'
);
