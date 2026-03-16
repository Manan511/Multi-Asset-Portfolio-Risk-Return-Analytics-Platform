"""
Phase 1: Data Extraction Layer
Multi-Asset Portfolio Risk & Return Analytics Platform

Extracts historical Adj Close prices for Indian equity assets and ^NSEI index
using yfinance, transforms to tall format, and exports to CSV.

Permitted Libraries: yfinance, pandas, datetime ONLY
"""

import yfinance as yf
import pandas as pd
from datetime import date, timedelta


# ── Configuration ────────────────────────────────────────────────────────────

ASSETS = ['RELIANCE.NS', 'HDFCBANK.NS', 'TCS.NS', '^NSEI']

END_DATE   = date.today()
START_DATE = END_DATE - timedelta(days=5 * 365)   # Exactly last 5 years

OUTPUT_FILE = 'portfolio_raw_data.csv'


# ── Step 1: Download Adj Close prices ────────────────────────────────────────

print(f"Downloading data from {START_DATE} to {END_DATE} ...")

raw_data = yf.download(
    tickers     = ASSETS,
    start       = START_DATE.strftime('%Y-%m-%d'),
    end         = END_DATE.strftime('%Y-%m-%d'),
    auto_adjust = False        # Keeps 'Adj Close' as a separate column
)

# Extract only the Adj Close prices
adj_close_df = raw_data['Adj Close']

print(f"Raw shape: {adj_close_df.shape}")


# ── Step 2: Reset index — converts DatetimeIndex to a plain 'Date' column ────

adj_close_df = adj_close_df.reset_index()

# Rename the index column in case yfinance returns it as 'index' or 'Datetime'
if 'index' in adj_close_df.columns:
    adj_close_df.rename(columns={'index': 'Date'}, inplace=True)
elif 'Datetime' in adj_close_df.columns:
    adj_close_df.rename(columns={'Datetime': 'Date'}, inplace=True)

# Ensure Date column is present
assert 'Date' in adj_close_df.columns, "'Date' column missing after reset_index()"


# ── Step 3: Melt wide to tall format ─────────────────────────────────────────

tall_df = pd.melt(
    adj_close_df,
    id_vars    = ['Date'],
    var_name   = 'Asset_Symbol',
    value_name = 'Adj_Close'
)

print(f"Tall shape before dropna: {tall_df.shape}")


# ── Step 4: Drop null values in-place ────────────────────────────────────────

tall_df.dropna(inplace=True)

print(f"Tall shape after dropna:  {tall_df.shape}")


# ── Step 5: Ensure Date column is date-only (no time component) ──────────────

tall_df['Date'] = pd.to_datetime(tall_df['Date']).dt.date


# ── Step 6: Round Adj_Close to 4 decimal places (matches DB NUMERIC(15,4)) ───

tall_df['Adj_Close'] = tall_df['Adj_Close'].round(4)


# ── Step 7: Sort for readability ──────────────────────────────────────────────

tall_df.sort_values(by=['Asset_Symbol', 'Date'], inplace=True)

print(tall_df.head(10))
print(f"\nAssets found : {tall_df['Asset_Symbol'].unique()}")
print(f"Date range   : {tall_df['Date'].min()} to {tall_df['Date'].max()}")
print(f"Total rows   : {len(tall_df)}")


# ── Step 8: Export to CSV ─────────────────────────────────────────────────────

tall_df.to_csv(OUTPUT_FILE, index=False)

print(f"\n[OK] Data saved to '{OUTPUT_FILE}' ({len(tall_df)} rows)")
