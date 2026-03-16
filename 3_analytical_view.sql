-- =============================================================================
-- Phase 2B: Analytical SQL Engine — vw_Portfolio_Analytics
-- Multi-Asset Portfolio Risk & Return Analytics Platform
-- Database: PostgreSQL (STRICTLY required)
--
-- Constraints honoured:
--   * Built entirely with CTEs (WITH clause)
--   * Window functions: LAG, MAX OVER, SUM OVER, EXP/LN for cumulative growth
--   * Adj_Close sourced from Fact_Prices where it is NUMERIC(15,4)
-- =============================================================================

DROP VIEW IF EXISTS vw_Portfolio_Analytics;

CREATE OR REPLACE VIEW vw_Portfolio_Analytics AS

-- ─────────────────────────────────────────────────────────────────────────────
-- CTE 1 | base_prices
-- Join Fact_Prices with Dim_Assets to enrich with asset metadata
-- ─────────────────────────────────────────────────────────────────────────────
WITH base_prices AS (
    SELECT
        fp.Date,
        fp.Asset_Symbol,
        da.Asset_Name,
        da.Asset_Type,
        fp.Adj_Close
    FROM  Fact_Prices fp
    JOIN  Dim_Assets  da USING (Asset_Symbol)
),

-- ─────────────────────────────────────────────────────────────────────────────
-- CTE 2 | with_daily_return
-- Daily Return using the LAG window function (mandatory per spec)
--
-- Formula:
--   Daily_Return = (Adj_Close - LAG(Adj_Close,1) OVER (...))
--                / LAG(Adj_Close,1) OVER (...)
-- ─────────────────────────────────────────────────────────────────────────────
with_daily_return AS (
    SELECT
        Date,
        Asset_Symbol,
        Asset_Name,
        Asset_Type,
        Adj_Close,

        -- Mandatory LAG-based Daily Return
        (
            Adj_Close
            - LAG(Adj_Close, 1) OVER (PARTITION BY Asset_Symbol ORDER BY Date)
        )
        /
        LAG(Adj_Close, 1) OVER (PARTITION BY Asset_Symbol ORDER BY Date)
            AS Daily_Return

    FROM base_prices
),

-- ─────────────────────────────────────────────────────────────────────────────
-- CTE 3 | with_peak_and_drawdown
-- Running Peak (mandatory MAX window function) + Drawdown Percentage
--
-- Running_Peak formula:
--   MAX(Adj_Close) OVER (PARTITION BY Asset_Symbol ORDER BY Date)
--
-- Drawdown_Percentage formula:
--   (Adj_Close - Running_Peak) / Running_Peak
-- ─────────────────────────────────────────────────────────────────────────────
with_peak_and_drawdown AS (
    SELECT
        Date,
        Asset_Symbol,
        Asset_Name,
        Asset_Type,
        Adj_Close,
        Daily_Return,

        -- Mandatory MAX-based Running Peak
        MAX(Adj_Close) OVER (
            PARTITION BY Asset_Symbol
            ORDER BY Date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS Running_Peak

    FROM with_daily_return
),

-- ─────────────────────────────────────────────────────────────────────────────
-- CTE 4 | with_cumulative_growth
-- Cumulative Growth using log-sum trick (mandatory; avoids recursive queries)
--
-- Formula:
--   EXP( SUM( LN(1 + COALESCE(Daily_Return, 0)) )
--        OVER (PARTITION BY Asset_Symbol ORDER BY Date) )
-- ─────────────────────────────────────────────────────────────────────────────
with_cumulative_growth AS (
    SELECT
        Date,
        Asset_Symbol,
        Asset_Name,
        Asset_Type,
        Adj_Close,
        Daily_Return,
        Running_Peak,

        -- Drawdown Percentage (derived from Running_Peak)
        (Adj_Close - Running_Peak) / Running_Peak AS Drawdown_Percentage,

        -- Mandatory EXP/SUM(LN()) cumulative growth
        EXP(
            SUM(
                LN(1 + COALESCE(Daily_Return, 0))
            ) OVER (
                PARTITION BY Asset_Symbol
                ORDER BY Date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        ) AS Cumulative_Growth

    FROM with_peak_and_drawdown
)

-- ─────────────────────────────────────────────────────────────────────────────
-- Final SELECT — expose all computed columns to Power BI
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    Date,
    Asset_Symbol,
    Asset_Name,
    Asset_Type,
    Adj_Close,
    Daily_Return,
    Running_Peak,
    Drawdown_Percentage,
    Cumulative_Growth
FROM with_cumulative_growth
ORDER BY Asset_Symbol, Date;


-- =============================================================================
-- Quick sanity-check queries (run after loading data)
-- =============================================================================

-- SELECT Asset_Symbol, COUNT(*) AS rows, MIN(Date), MAX(Date)
-- FROM   vw_Portfolio_Analytics
-- GROUP  BY Asset_Symbol
-- ORDER  BY Asset_Symbol;

-- SELECT * FROM vw_Portfolio_Analytics
-- WHERE  Asset_Symbol = 'TCS.NS'
-- ORDER  BY Date
-- LIMIT  20;

