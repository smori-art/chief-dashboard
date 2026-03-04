-- ============================================================
-- Chief Dashboard - MART Layer DDL
-- Dataset: chief_mart
-- Purpose: Pre-aggregated tables for dashboard performance
-- ============================================================

-- Mart: Monthly Sales by Store x Department
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_sales_monthly` (
    ym STRING NOT NULL,
    year INT64,
    month INT64,
    store_id STRING NOT NULL,
    store_name STRING,
    dept_id STRING NOT NULL,
    dept_name STRING,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    discount_amount_ex_tax NUMERIC,
    qty NUMERIC,
    receipts INT64,
    refund_amount NUMERIC,
    net_sales_after_refund NUMERIC,
    cogs NUMERIC,
    gross_profit NUMERIC,
    gross_margin_pct FLOAT64,
    discount_rate_pct FLOAT64,
    -- Year-over-year
    gross_sales_yoy NUMERIC,
    net_sales_yoy NUMERIC,
    gross_profit_yoy NUMERIC,
    gross_margin_yoy_diff FLOAT64,
    -- Month-over-month
    gross_sales_mom NUMERIC,
    net_sales_mom NUMERIC,
    gross_profit_mom NUMERIC,
    gross_margin_mom_diff FLOAT64,
    -- Composition
    sales_composition_pct FLOAT64,
    profit_composition_pct FLOAT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY RANGE_BUCKET(year, GENERATE_ARRAY(2020, 2030, 1))
CLUSTER BY store_id, dept_id;

-- Mart: Monthly Sales by Store x Department x Category
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_sales_monthly_category` (
    ym STRING NOT NULL,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    cat_l STRING,
    cat_m STRING,
    cat_s STRING,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    discount_amount_ex_tax NUMERIC,
    qty NUMERIC,
    cogs NUMERIC,
    gross_profit NUMERIC,
    gross_margin_pct FLOAT64,
    discount_rate_pct FLOAT64,
    gross_sales_yoy NUMERIC,
    gross_margin_yoy_diff FLOAT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY store_id, dept_id, cat_l;

-- Mart: Daily Sales (for trend charts and forecast)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_sales_daily` (
    date DATE NOT NULL,
    ym STRING,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    gross_sales_ex_tax NUMERIC,
    net_sales_ex_tax NUMERIC,
    discount_amount_ex_tax NUMERIC,
    qty NUMERIC,
    receipts INT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY date
CLUSTER BY store_id, dept_id;

-- Mart: OOS (Out-of-Stock) Analysis
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_oos_receipt_based` (
    date DATE NOT NULL,
    store_id STRING NOT NULL,
    sku STRING NOT NULL,
    dept_id STRING,
    product_name STRING,
    expected_qty NUMERIC,
    actual_qty NUMERIC,
    is_oos_suspect BOOL,
    opportunity_loss_amount NUMERIC,
    dow INT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY date
CLUSTER BY store_id, dept_id;

-- Mart: Forecast (Monthly landing estimate)
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_forecast_monthly` (
    ym STRING NOT NULL,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    actual_to_date NUMERIC,
    elapsed_days INT64,
    total_days INT64,
    forecast_sales NUMERIC,
    forecast_gross_profit NUMERIC,
    forecast_method STRING DEFAULT 'linear_extrapolation',
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY store_id, dept_id;

-- Mart: Inventory Monthly
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_inventory_monthly` (
    ym STRING NOT NULL,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    onhand_qty NUMERIC,
    onhand_amount NUMERIC,
    inventory_method STRING,
    adjustment_qty NUMERIC,
    adjustment_amount NUMERIC,
    inventory_turnover FLOAT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY store_id, dept_id;

-- Mart: Waste & Discount Monthly
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_MART}.mart_waste_discount_monthly` (
    ym STRING NOT NULL,
    store_id STRING NOT NULL,
    dept_id STRING NOT NULL,
    waste_qty NUMERIC,
    waste_amount_ex_tax NUMERIC,
    waste_rate_pct FLOAT64,
    markdown_qty NUMERIC,
    markdown_amount_ex_tax NUMERIC,
    markdown_rate_pct FLOAT64,
    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY store_id, dept_id;
