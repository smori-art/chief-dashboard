-- ============================================================
-- View: Monthly Sales KPIs by Store x Department
-- Used by: Executive Summary, Department View, Store View
-- ============================================================
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET_MART}.v_kpi_sales_monthly` AS
WITH current_period AS (
    SELECT
        d.ym,
        d.year,
        d.month,
        f.store_id,
        COALESCE(f.dept_id, 'unknown') AS dept_id,
        SUM(f.gross_sales_ex_tax) AS gross_sales_ex_tax,
        SUM(f.net_sales_ex_tax) AS net_sales_ex_tax,
        SUM(f.discount_amount_ex_tax) AS discount_amount_ex_tax,
        SUM(f.qty) AS qty
    FROM `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` f
    JOIN `${PROJECT_ID}.${DATASET_STG}.dim_date` d ON f.date = d.date
    GROUP BY d.ym, d.year, d.month, f.store_id, f.dept_id
),
refunds AS (
    SELECT
        FORMAT_DATE('%Y-%m', s.date) AS ym,
        s.store_id,
        SUM(CASE WHEN s.is_refund THEN s.amount ELSE 0 END) AS refund_amount
    FROM `${PROJECT_ID}.${DATASET_STG}.f_settlement` s
    GROUP BY 1, 2
),
store_dim AS (
    SELECT store_id, store_name FROM `${PROJECT_ID}.${DATASET_STG}.dim_store`
),
dept_dim AS (
    SELECT dept_id, dept_name, cost_method FROM `${PROJECT_ID}.${DATASET_STG}.dim_department`
),
-- Cost approximation: use standard_cost from product master as proxy
cost_data AS (
    SELECT
        d.ym,
        f.store_id,
        COALESCE(f.dept_id, 'unknown') AS dept_id,
        SUM(f.qty * COALESCE(p.standard_cost, 0)) AS cogs
    FROM `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` f
    JOIN `${PROJECT_ID}.${DATASET_STG}.dim_date` d ON f.date = d.date
    LEFT JOIN `${PROJECT_ID}.${DATASET_STG}.dim_product` p ON f.sku = p.sku
    GROUP BY d.ym, f.store_id, f.dept_id
),
combined AS (
    SELECT
        cp.ym,
        cp.year,
        cp.month,
        cp.store_id,
        COALESCE(sd.store_name, cp.store_id) AS store_name,
        cp.dept_id,
        COALESCE(dd.dept_name, cp.dept_id) AS dept_name,
        dd.cost_method,
        cp.gross_sales_ex_tax,
        cp.net_sales_ex_tax,
        cp.discount_amount_ex_tax,
        cp.qty,
        COALESCE(r.refund_amount, 0) AS refund_amount,
        cp.net_sales_ex_tax - COALESCE(r.refund_amount, 0) AS net_sales_after_refund,
        COALESCE(cd.cogs, 0) AS cogs,
        cp.net_sales_ex_tax - COALESCE(cd.cogs, 0) AS gross_profit,
        SAFE_DIVIDE(
            cp.net_sales_ex_tax - COALESCE(cd.cogs, 0),
            NULLIF(cp.net_sales_ex_tax, 0)
        ) * 100 AS gross_margin_pct,
        SAFE_DIVIDE(
            cp.discount_amount_ex_tax,
            NULLIF(cp.gross_sales_ex_tax, 0)
        ) * 100 AS discount_rate_pct
    FROM current_period cp
    LEFT JOIN refunds r ON cp.ym = r.ym AND cp.store_id = r.store_id
    LEFT JOIN store_dim sd ON cp.store_id = sd.store_id
    LEFT JOIN dept_dim dd ON cp.dept_id = dd.dept_id
    LEFT JOIN cost_data cd ON cp.ym = cd.ym AND cp.store_id = cd.store_id AND cp.dept_id = cd.dept_id
),
-- YoY comparison
with_yoy AS (
    SELECT
        c.*,
        prev.gross_sales_ex_tax AS gross_sales_prev_year,
        prev.net_sales_ex_tax AS net_sales_prev_year,
        prev.gross_profit AS gross_profit_prev_year,
        prev.gross_margin_pct AS gross_margin_prev_year,
        c.gross_sales_ex_tax - COALESCE(prev.gross_sales_ex_tax, 0) AS gross_sales_yoy,
        c.net_sales_ex_tax - COALESCE(prev.net_sales_ex_tax, 0) AS net_sales_yoy,
        c.gross_profit - COALESCE(prev.gross_profit, 0) AS gross_profit_yoy,
        c.gross_margin_pct - COALESCE(prev.gross_margin_pct, 0) AS gross_margin_yoy_diff
    FROM combined c
    LEFT JOIN combined prev
        ON c.store_id = prev.store_id
        AND c.dept_id = prev.dept_id
        AND c.year = prev.year + 1
        AND c.month = prev.month
)
SELECT
    *,
    -- Composition ratios (within same ym)
    SAFE_DIVIDE(
        net_sales_ex_tax,
        SUM(net_sales_ex_tax) OVER (PARTITION BY ym, store_id)
    ) * 100 AS sales_composition_pct,
    SAFE_DIVIDE(
        gross_profit,
        NULLIF(SUM(gross_profit) OVER (PARTITION BY ym, store_id), 0)
    ) * 100 AS profit_composition_pct
FROM with_yoy;
