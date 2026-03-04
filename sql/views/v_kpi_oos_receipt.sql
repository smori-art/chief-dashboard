-- ============================================================
-- View: Out-of-Stock Detection (Receipt-based Estimation)
-- Method: Compare actual daily sales vs expected (median of same DOW, last 8 weeks)
-- ============================================================
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET_MART}.v_kpi_oos_receipt` AS
WITH daily_sku_sales AS (
    SELECT
        f.date,
        f.store_id,
        f.sku,
        f.dept_id,
        d.dow,
        SUM(f.qty) AS actual_qty,
        SUM(f.net_sales_ex_tax) AS actual_sales
    FROM `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` f
    JOIN `${PROJECT_ID}.${DATASET_STG}.dim_date` d ON f.date = d.date
    GROUP BY f.date, f.store_id, f.sku, f.dept_id, d.dow
),
-- Calculate expected sales: median of same DOW, last 8 weeks
expected_sales AS (
    SELECT
        ds.date AS ref_date,
        ds.store_id,
        ds.sku,
        ds.dept_id,
        ds.dow,
        -- Get historical same-DOW data
        PERCENTILE_CONT(hist.actual_qty, 0.5) OVER (
            PARTITION BY ds.store_id, ds.sku, ds.dow
            ORDER BY hist.date
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
        ) AS expected_qty,
        PERCENTILE_CONT(hist.actual_sales, 0.5) OVER (
            PARTITION BY ds.store_id, ds.sku, ds.dow
            ORDER BY hist.date
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
        ) AS expected_sales
    FROM daily_sku_sales ds
    LEFT JOIN daily_sku_sales hist
        ON ds.store_id = hist.store_id
        AND ds.sku = hist.sku
        AND ds.dow = hist.dow
        AND hist.date BETWEEN DATE_SUB(ds.date, INTERVAL 56 DAY) AND DATE_SUB(ds.date, INTERVAL 1 DAY)
),
oos_detection AS (
    SELECT
        ds.date,
        ds.store_id,
        ds.sku,
        ds.dept_id,
        p.product_name,
        ds.actual_qty,
        COALESCE(es.expected_qty, 0) AS expected_qty,
        ds.actual_sales,
        COALESCE(es.expected_sales, 0) AS expected_sales,
        ds.dow,
        -- OOS suspect: actual is 0 or less than 20% of expected
        CASE
            WHEN COALESCE(es.expected_qty, 0) > 0
                AND ds.actual_qty <= es.expected_qty * 0.2
            THEN TRUE
            ELSE FALSE
        END AS is_oos_suspect,
        -- Opportunity loss estimate
        CASE
            WHEN COALESCE(es.expected_qty, 0) > 0
                AND ds.actual_qty <= es.expected_qty * 0.2
            THEN COALESCE(es.expected_sales, 0) - ds.actual_sales
            ELSE 0
        END AS opportunity_loss_amount
    FROM daily_sku_sales ds
    LEFT JOIN expected_sales es
        ON ds.date = es.ref_date
        AND ds.store_id = es.store_id
        AND ds.sku = es.sku
    LEFT JOIN `${PROJECT_ID}.${DATASET_STG}.dim_product` p ON ds.sku = p.sku
)
SELECT * FROM oos_detection;
