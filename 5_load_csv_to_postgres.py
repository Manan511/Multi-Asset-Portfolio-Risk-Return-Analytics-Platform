"""
Phase 2 Helper: Load portfolio_raw_data.csv into PostgreSQL Fact_Prices table.

Prerequisites:
  pip install psycopg2-binary pandas
  (yfinance already installed from Phase 1)

Update DB_CONFIG below with your PostgreSQL credentials before running.
"""

import psycopg2
import psycopg2.extras
import pandas as pd


# ── Database connection config — update these ─────────────────────────────────
DB_CONFIG = {
    'host':     'localhost',
    'port':     5432,
    'dbname':   'portfolio_db',       # change to your database name
    'user':     'postgres',           # change to your username
    'password': 'your_password_here', # change to your password
}

CSV_FILE = 'portfolio_raw_data.csv'


# ── Load CSV ──────────────────────────────────────────────────────────────────

print(f"Reading {CSV_FILE} ...")
df = pd.read_csv(CSV_FILE, parse_dates=['Date'])
df['Date'] = df['Date'].dt.date   # Convert to Python date for psycopg2
print(f"  Rows to load: {len(df)}")


# ── Insert into Fact_Prices ───────────────────────────────────────────────────

INSERT_SQL = """
    INSERT INTO Fact_Prices (Date, Asset_Symbol, Adj_Close)
    VALUES %s
    ON CONFLICT (Date, Asset_Symbol) DO UPDATE
        SET Adj_Close = EXCLUDED.Adj_Close;
"""

rows = list(df[['Date', 'Asset_Symbol', 'Adj_Close']].itertuples(index=False, name=None))

print("Connecting to PostgreSQL ...")
conn = psycopg2.connect(**DB_CONFIG)
cur  = conn.cursor()

print("Inserting rows (upsert) ...")
psycopg2.extras.execute_values(cur, INSERT_SQL, rows, page_size=500)

conn.commit()
print(f"[OK] {cur.rowcount} rows upserted into Fact_Prices.")

cur.close()
conn.close()
