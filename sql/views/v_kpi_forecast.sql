-- ============================================================
-- View: Monthly Forecast (Landing Estimate)
-- Purpose: Generate current month forecast based on actual-to-date
-- ============================================================
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET_MART}.v_kpi_forecast` AS
WITH current_month AS (
    SELECT FORMAT_DATE('%Y-%m', CURRENT_DATE('Asia/Bangkok')) AS current_ym
),
daily_actuals AS (
    SELECT
        FORMAT_DATE('%Y-%m', f.date) AS ym,
        f.store_id,
        COALESCE(f.dept_id, 'unknown') AS dept_id,
        SUM(f.net_sales_ex_tax) AS actual_to_date,
        COUNT(DISTINCT f.date) AS elapsed_days
    FROM `${PROJECT_ID}.${DATASET_STG}.f_sales_item_daily` f
    CROSS JOIN current_month cm
    WHERE FORMAT_DATE('%Y-%m', f.date) = cm.current_ym
    GROUP BY 1, 2, 3
),
month_info AS (
    SELECT
        ym,
        MAX(days_in_month) AS total_days
    FROM `${PROJECT_ID}.${DATASET_STG}.dim_date`
    GROUP BY ym
)
SELECT
    da.ym,
    da.store_id,
    da.dept_id,
    da.actual_to_date,
    da.elapsed_days,
    mi.total_days,
    -- Linear extrapolation forecast
    CASE
        WHEN da.elapsed_days >= 7 THEN
            ROUND(da.actual_to_date / da.elapsed_days * mi.total_days, 2)
        ELSE NULL  -- Not enough data for forecast
    END AS forecast_sales,
    'linear_extrapolation' AS forecast_method
FROM daily_actuals da
LEFT JOIN month_info mi ON da.ym = mi.ym;
