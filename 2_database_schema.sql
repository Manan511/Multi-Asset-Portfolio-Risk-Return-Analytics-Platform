-- =============================================================================
-- Phase 2A: Database Schema Design
-- Multi-Asset Portfolio Risk & Return Analytics Platform
-- Database: PostgreSQL (STRICTLY required — MySQL / SQL Server NOT permitted)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. Setup: Create a dedicated schema (optional but recommended)
-- -----------------------------------------------------------------------------

-- DROP SCHEMA IF EXISTS portfolio CASCADE;
-- CREATE SCHEMA portfolio;
-- SET search_path = portfolio;


-- =============================================================================
-- TABLE 1: Dim_Assets  (Dimension / Lookup table)
-- =============================================================================

DROP TABLE IF EXISTS Fact_Prices CASCADE;   -- drop child first
DROP TABLE IF EXISTS Dim_Assets  CASCADE;

CREATE TABLE Dim_Assets (
    Asset_Symbol  VARCHAR(20)  NOT NULL,                -- Primary Key
    Asset_Name    VARCHAR(100) NOT NULL,
    Asset_Type    VARCHAR(50)  NOT NULL,                -- e.g. 'Equity', 'Index'

    CONSTRAINT pk_dim_assets PRIMARY KEY (Asset_Symbol)
);

-- Seed the dimension table with our four assets
INSERT INTO Dim_Assets (Asset_Symbol, Asset_Name, Asset_Type) VALUES
    ('RELIANCE.NS',  'Reliance Industries Ltd',  'Equity'),
    ('HDFCBANK.NS',  'HDFC Bank Ltd',             'Equity'),
    ('TCS.NS',       'Tata Consultancy Services', 'Equity'),
    ('^NSEI',        'NIFTY 50 Index',            'Index');


-- =============================================================================
-- TABLE 2: Fact_Prices  (Fact / Transactional table)
-- =============================================================================

CREATE TABLE Fact_Prices (
    Date          DATE           NOT NULL,
    Asset_Symbol  VARCHAR(20)    NOT NULL,              -- Foreign Key → Dim_Assets
    Adj_Close     NUMERIC(15, 4) NOT NULL,              -- STRICT: NUMERIC(15,4) only

    CONSTRAINT pk_fact_prices
        PRIMARY KEY (Date, Asset_Symbol),

    CONSTRAINT fk_fact_prices_asset
        FOREIGN KEY (Asset_Symbol)
        REFERENCES Dim_Assets (Asset_Symbol)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- Index to speed up analytical queries partitioned / ordered by Asset + Date
CREATE INDEX IF NOT EXISTS idx_fact_prices_symbol_date
    ON Fact_Prices (Asset_Symbol, Date);


-- =============================================================================
-- How to bulk-load portfolio_raw_data.csv into Fact_Prices
-- (Run from psql or adjust for your client)
-- =============================================================================
-- \COPY Fact_Prices (Date, Asset_Symbol, Adj_Close)
-- FROM 'portfolio_raw_data.csv'
-- WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',');

