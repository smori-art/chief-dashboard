-- ============================================================
-- Chief Dashboard - STAGING Layer DDL
-- Dataset: chief_stg
-- Purpose: Normalized, type-converted, deduplicated data
-- ============================================================

-- Dimension: Stores
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.dim_store` (
    store_id STRING NOT NULL,
    store_name STRING NOT NULL,
    open_date DATE,
    region STRING,
    timezone STRING DEFAULT 'Asia/Bangkok',
    is_active BOOL DEFAULT TRUE,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Dimension: Departments
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.dim_department` (
    dept_id STRING NOT NULL,
    dept_name STRING NOT NULL,
    cost_method STRING NOT NULL DEFAULT 'purchase_cost',  -- moving_average / purchase_cost
    inventory_method STRING NOT NULL DEFAULT 'physical_count',  -- theoretical / physical_count
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Seed department data
MERGE `${PROJECT_ID}.${DATASET_STG}.dim_department` AS t
USING (
    SELECT 'food' AS dept_id, '食品' AS dept_name, 'moving_average' AS cost_method, 'theoretical' AS inventory_method
    UNION ALL SELECT 'produce', '青果', 'purchase_cost', 'physical_count'
    UNION ALL SELECT 'seafood', '鮮魚', 'purchase_cost', 'physical_count'
    UNION ALL SELECT 'meat', '精肉', 'purchase_cost', 'physical_count'
    UNION ALL SELECT 'deli', '惣菜', 'purchase_cost', 'physical_count'
    UNION ALL SELECT 'store_mgmt', '店舗管理', 'purchase_cost', 'physical_count'
) AS s
ON t.dept_id = s.dept_id
WHEN MATCHED THEN
    UPDATE SET dept_name = s.dept_name, cost_method = s.cost_method, inventory_method = s.inventory_method, _updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (dept_id, dept_name, cost_method, inventory_method)
    VALUES (s.dept_id, s.dept_name, s.cost_method, s.inventory_method);

-- Dimension: Products
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.dim_product` (
    sku STRING NOT NULL,
    product_name STRING,
    dept_id STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    uom STRING,
    standard_cost NUMERIC,
    active_flag BOOL DEFAULT TRUE,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Dimension: Date (generated)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.dim_date` (
    date DATE NOT NULL,
    year INT64,
    month INT64,
    ym STRING,
    week INT64,
    dow INT64,
    dow_name STRING,
    is_month_end BOOL,
    days_in_month INT64
);

-- Populate dim_date for 5 years (2022-2027)
MERGE `${PROJECT_ID}.${DATASET_STG}.dim_date` AS t
USING (
    SELECT
        d AS date,
        EXTRACT(YEAR FROM d) AS year,
        EXTRACT(MONTH FROM d) AS month,
        FORMAT_DATE('%Y-%m', d) AS ym,
        EXTRACT(ISOWEEK FROM d) AS week,
        EXTRACT(DAYOFWEEK FROM d) AS dow,
        FORMAT_DATE('%A', d) AS dow_name,
        d = LAST_DAY(d) AS is_month_end,
        EXTRACT(DAY FROM LAST_DAY(d)) AS days_in_month
    FROM UNNEST(GENERATE_DATE_ARRAY('2022-01-01', '2027-12-31')) AS d
) AS s
ON t.date = s.date
WHEN NOT MATCHED THEN
    INSERT (date, year, month, ym, week, dow, dow_name, is_month_end, days_in_month)
    VALUES (s.date, s.year, s.month, s.ym, s.week, s.dow, s.dow_name, s.is_month_end, s.days_in_month);

-- Dimension: Time bands (hourly)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.dim_timeband` (
    timeband_id STRING NOT NULL,
    start_time TIME,
    end_time TIME,
    label STRING
);

MERGE `${PROJECT_ID}.${DATASET_STG}.dim_timeband` AS t
USING (
    SELECT
        FORMAT('%02d', h) AS timeband_id,
        TIME(h, 0, 0) AS start_time,
        TIME(IF(h = 23, 23, h + 1), IF(h = 23, 59, 0), IF(h = 23, 59, 0)) AS end_time,
        FORMAT('%02d:00-%02d:00', h, IF(h = 23, 24, h + 1)) AS label
    FROM UNNEST(GENERATE_ARRAY(0, 23)) AS h
) AS s
ON t.timeband_id = s.timeband_id
WHEN NOT MATCHED THEN
    INSERT (timeband_id, start_time, end_time, label)
    VALUES (s.timeband_id, s.start_time, s.end_time, s.label);

-- Fact: Sales Item Daily (deduplicated)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    sku STRING NOT NULL,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    qty NUMERIC,
    discount_amount_ex_tax NUMERIC,
    dept_id STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id, dept_id;

-- Fact: Sales Store Daily (deduplicated)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_sales_store_daily` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    receipts INT64,
    qty NUMERIC,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id;

-- Fact: Receipt Lines (deduplicated)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_receipt_line` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    receipt_id STRING NOT NULL,
    line_no INT64 NOT NULL,
    sku STRING,
    qty NUMERIC,
    unit_price_ex_tax NUMERIC,
    gross_amount_ex_tax NUMERIC,
    discount_amount_ex_tax NUMERIC,
    net_amount_ex_tax NUMERIC,
    time TIME,
    dept_id STRING,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id, receipt_id;

-- Fact: Settlement (deduplicated)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_settlement` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    receipt_id STRING,
    tender_type STRING,
    amount NUMERIC,
    is_refund BOOL,
    refund_reason_code STRING,
    original_receipt_id STRING,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id;

-- Fact: Sales Dept Timeband Daily
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_sales_dept_timeband_daily` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    timeband_id STRING NOT NULL,
    gross_sales_ex_tax NUMERIC,
    qty NUMERIC,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id, dept_id;

-- Fact: Inventory Monthly
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_inventory_monthly` (
    month_end_date DATE NOT NULL,
    store_id STRING NOT NULL,
    sku STRING,
    dept_id STRING,
    cat_l STRING,
    onhand_qty NUMERIC,
    onhand_amount NUMERIC,
    is_physical_count BOOL,
    for_food_theoretical_flag BOOL,
    adjustment_qty NUMERIC,
    adjustment_amount NUMERIC,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY month_end_date
CLUSTER BY store_id;

-- Fact: Waste & Discount Daily
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_STG}.f_waste_discount_daily` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    sku STRING,
    dept_id STRING,
    cat_l STRING,
    waste_qty NUMERIC,
    waste_amount_ex_tax NUMERIC,
    markdown_qty NUMERIC,
    markdown_amount_ex_tax NUMERIC,
    _source_file STRING,
    _imported_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY store_id;
