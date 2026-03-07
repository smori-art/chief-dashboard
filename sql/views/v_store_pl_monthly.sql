-- ============================================================
-- Store P&L Monthly View
-- Dataset: chief_mart
-- Purpose: Monthly P&L by store with YoY comparison
-- ============================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET_MART}.v_store_pl_monthly` AS
SELECT
    pl.ym,
    pl.store_id,
    s.store_name,
    pl.net_sales,
    pl.cogs,
    pl.gross_profit,
    pl.gross_margin_pct,
    pl.personnel_expense,
    pl.rent_expense,
    pl.utility_expense,
    pl.depreciation_expense,
    pl.other_opex,
    pl.total_opex,
    pl.operating_profit,
    pl.operating_margin_pct,
    -- Ratios to sales
    SAFE_DIVIDE(pl.personnel_expense, pl.net_sales) * 100 AS personnel_ratio_pct,
    SAFE_DIVIDE(pl.rent_expense, pl.net_sales) * 100 AS rent_ratio_pct,
    SAFE_DIVIDE(pl.utility_expense, pl.net_sales) * 100 AS utility_ratio_pct,
    SAFE_DIVIDE(pl.depreciation_expense, pl.net_sales) * 100 AS depreciation_ratio_pct,
    SAFE_DIVIDE(pl.other_opex, pl.net_sales) * 100 AS other_opex_ratio_pct,
    SAFE_DIVIDE(pl.total_opex, pl.net_sales) * 100 AS total_opex_ratio_pct
FROM `${PROJECT_ID}.${DATASET_STG}.f_store_pl_monthly` pl
LEFT JOIN `${PROJECT_ID}.${DATASET_STG}.dim_store` s
    ON pl.store_id = s.store_id
ORDER BY pl.ym DESC, pl.store_id;
