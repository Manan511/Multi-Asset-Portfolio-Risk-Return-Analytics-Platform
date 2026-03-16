# Multi-Asset Portfolio Risk & Return Analytics Platform

End-to-end data pipeline + BI dashboard for Indian equity portfolio analytics.

## Project Structure

```
portfolio-risk-analytics/
├── 1_data_extraction.py        # Phase 1 — Download & transform price data
├── 2_database_schema.sql       # Phase 2A — PostgreSQL tables (Dim_Assets, Fact_Prices)
├── 3_analytical_view.sql       # Phase 2B — vw_Portfolio_Analytics (CTE + Window Fns)
├── 4_powerbi_dax_measures.md   # Phase 3 — DAX measures & dashboard layout guide
├── 5_load_csv_to_postgres.py   # Helper — Bulk-load CSV into PostgreSQL
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Quick Start

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Extract data
```bash
python 1_data_extraction.py
# Outputs: portfolio_raw_data.csv
```

### Step 3 — Set up PostgreSQL
```bash
psql -U postgres -d your_db -f 2_database_schema.sql
psql -U postgres -d your_db -f 3_analytical_view.sql
```

### Step 4 — Load data
```bash
# Option A — via psql COPY (fastest)
psql -U postgres -d your_db -c "\COPY Fact_Prices (Date, Asset_Symbol, Adj_Close) FROM 'portfolio_raw_data.csv' WITH (FORMAT CSV, HEADER TRUE)"

# Option B — via Python helper (update DB credentials in the script first)
python 5_load_csv_to_postgres.py
```

### Step 5 — Power BI
Follow the instructions in `4_powerbi_dax_measures.md` to:
- Connect Power BI to the `vw_Portfolio_Analytics` view
- Create all 4 DAX measures
- Build the 3 dashboard pages

## Assets Tracked
| Symbol | Name | Type |
|--------|------|------|
| RELIANCE.NS | Reliance Industries Ltd | Equity |
| HDFCBANK.NS | HDFC Bank Ltd | Equity |
| TCS.NS | Tata Consultancy Services | Equity |
| ^NSEI | NIFTY 50 Index | Index |

## Tech Stack
- **Python**: yfinance · pandas · datetime
- **Database**: PostgreSQL (NUMERIC(15,4) precision)
- **BI Tool**: Power BI Desktop with DAX
