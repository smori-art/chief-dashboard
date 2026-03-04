-- ============================================================
-- View: Category Drilldown (Department > Large > Medium > Small)
-- Used by: Department View for hierarchical analysis
-- ============================================================
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET_MART}.v_kpi_category_drilldown` AS
WITH category_sales AS (
    SELECT
        d.ym,
        f.store_id,
        f.dept_id,
        COALESCE(f.cat_l, 'その他') AS cat_l,
        COALESCE(f.cat_m, 'その他') AS cat_m,
        COALESCE(f.cat_s, 'その他') AS cat_s,
        SUM(f.gross_sales_ex_tax) AS gross_sales_ex_tax,
        SUM(f.net_sales_ex_tax) AS net_sales_ex_tax,
        SUM(f.discount_amount_ex_tax) AS discount_amount_ex_tax,
        SUM(f.qty) AS qty,
        SUM(f.qty * COALESCE(p.standard_cost, 0)) AS cogs
    FROM `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` f
    JOIN `${PROJECT_ID}.${DATASET_STG}.dim_date` d ON f.date = d.date
    LEFT JOIN `${PROJECT_ID}.${DATASET_STG}.dim_product` p ON f.sku = p.sku
    GROUP BY d.ym, f.store_id, f.dept_id, f.cat_l, f.cat_m, f.cat_s
),
with_profit AS (
    SELECT
        *,
        net_sales_ex_tax - cogs AS gross_profit,
        SAFE_DIVIDE(net_sales_ex_tax - cogs, NULLIF(net_sales_ex_tax, 0)) * 100 AS gross_margin_pct,
        SAFE_DIVIDE(discount_amount_ex_tax, NULLIF(gross_sales_ex_tax, 0)) * 100 AS discount_rate_pct
    FROM category_sales
),
with_yoy AS (
    SELECT
        c.*,
        c.gross_margin_pct - COALESCE(prev.gross_margin_pct, 0) AS gross_margin_yoy_diff,
        c.net_sales_ex_tax - COALESCE(prev.net_sales_ex_tax, 0) AS net_sales_yoy
    FROM with_profit c
    LEFT JOIN with_profit prev
        ON c.store_id = prev.store_id
        AND c.dept_id = prev.dept_id
        AND c.cat_l = prev.cat_l
        AND c.cat_m = prev.cat_m
        AND c.cat_s = prev.cat_s
        AND CAST(SUBSTR(c.ym, 1, 4) AS INT64) = CAST(SUBSTR(prev.ym, 1, 4) AS INT64) + 1
        AND SUBSTR(c.ym, 6, 2) = SUBSTR(prev.ym, 6, 2)
)
SELECT
    ym,
    store_id,
    dept_id,
    cat_l,
    cat_m,
    cat_s,
    gross_sales_ex_tax,
    net_sales_ex_tax,
    discount_amount_ex_tax,
    qty,
    cogs,
    gross_profit,
    gross_margin_pct,
    discount_rate_pct,
    gross_margin_yoy_diff,
    net_sales_yoy,
    -- Rankings within department
    RANK() OVER (
        PARTITION BY ym, store_id, dept_id
        ORDER BY gross_margin_pct ASC
    ) AS margin_worst_rank,
    RANK() OVER (
        PARTITION BY ym, store_id, dept_id
        ORDER BY discount_rate_pct DESC
    ) AS discount_worst_rank
FROM with_yoy;
