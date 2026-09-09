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
│
│   # Phase 4 — AI Narrative Report Generator
├── metrics_collector.py        # Bridge: existing metrics → structured metrics_summary
├── narrative_prompt.py         # The prompt, isolated for iteration (v1/v2)
├── llm_client.py               # Model backend — Gemini or Claude
├── narrative_generator.py      # Generate + number-traceability validation + output
├── 6_generate_narrative_report.py  # Entry point — one quarter
├── 7_validation_suite.py           # Entry point — all quarters, measured pass rate
│
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

---

# Phase 4 — AI Narrative Report Generator

## What this adds

The dashboard answers *what* the numbers are; it does not answer *what they mean*.
Somebody still has to sit down each quarter and write the commentary paragraph that
goes at the top of the report — reading the volatility move off one chart, the Sharpe
change off another, checking which correlation pair actually drove the risk, and
turning all of it into four sentences a non-quant can act on. That is maybe twenty
minutes of careful work per quarter, it is the same twenty minutes every quarter, and
it is the part most likely to get skipped when the deadline is tight.

This phase automates that paragraph. It takes the metrics the platform has **already
computed** — annualized volatility, Sharpe ratio, max drawdown, the correlation matrix,
rolling returns — and produces a short analyst-style narrative sized to sit in a text
box next to the charts. It is a companion to the Power BI dashboard, not a replacement
for it.

## How grounding works

The single credibility risk in an AI-written financial report is a number that looks
right and isn't. Two things in this design address that.

**The model is never in a position to compute anything.** `metrics_collector.py`
restates the formulas that already exist in this repo — the `LAG`/`MAX OVER` window
functions in `3_analytical_view.sql` and the four DAX measures in
`4_powerbi_dax_measures.md`, same 5% risk-free rate, same √252 annualization, same
`/365.25` CAGR — and serializes the results into a flat JSON dict. That dict is the
*entire* input to the model. It never sees a price series, so there is no arithmetic
for it to get wrong; its only job is to put the supplied figures into sentences.

**Every number it writes is checked back against the input.** After generation,
`validate_narrative()` regex-extracts every numeric literal from the prose and confirms
each one traces to a value in the `metrics_summary` it was given. Anything left over is
flagged: the narrative comes back marked `needs review` and the report file carries a
visible warning banner instead of shipping clean.

Two rules in that check are worth spelling out:

- **Signed asymmetry.** A source value of `-12.4` also licenses the unsigned `12.4`,
  because "a maximum drawdown of 12.4%" is quoting the figure rather than inventing one.
  The reverse is not permitted — a positive source value never licenses a negative one.
- **Stopword numbers.** Small integers (0–4) are exempt, because "declined for 3
  consecutive quarters" is English rather than a claim about the data. This is a
  deliberate loosening and it is the weakest part of the check.

### What this check does not catch

Traceability catches **fabricated** figures. It does not catch **misattributed** ones:
if the model reported the Sharpe ratio as `16.2` and the volatility as `0.94`, both
values are present in the input and both would trace clean. Catching that needs
field-level attribution, not set membership. Worth knowing before trusting the pass
rate as more than it is.

## Validation results

> **Not yet run against a live model.** The harness is complete and verified, but no
> real generation pass has been executed, so there is no measured pass rate to publish
> here yet. This section will be filled in with whatever the first real run produces —
> including any quarter that fails. See *Reproducing the validation* below.

What **has** been verified, using a stub model that returns deterministic text in place
of an API call:

| Check | Metric sets | Result |
|---|---|---|
| Well-formed narratives, all figures drawn from the input | 20 | 20/20 traced clean |
| Narrative with two fabricated figures appended | 1 | flagged `needs review`, `untraceable: [33.7, 21.9]` |

The negative case injects *"Volatility is now 33.7% above its five-year average of
21.9%"* — plausible-sounding, entirely invented, and caught. This confirms the harness
discriminates in both directions; it does not tell us how often a real model actually
strays, which is what the live run measures.

The 20 metric sets are real, not fixtures: they are every full quarter from
**Q4 2021 to Q3 2026**, built from 4,948 rows of actual NSE price history via
`1_data_extraction.py`. They span calm and volatile quarters, positive and negative
Sharpe ratios, and correlation pairs that both rose and fell.

## Example output

> **Pending the first live run.** Publishing a hand-written or stub-generated paragraph
> here as though a model produced it would defeat the point of the section, so it is
> left empty until there is a genuine one to paste.

For reference, this is a real metrics set the generator is handed (`Q3 2026`, produced
by `metrics_collector.py` from actual price data):

```json
{
  "period": "Q3 2026",
  "previous_period": "Q2 2026",
  "volatility": { "current": 16.2, "previous": 20.0, "unit": "%", "basis": "annualized" },
  "sharpe_ratio": { "current": -0.2, "previous": -0.92 },
  "max_drawdown": { "value": -5.8, "unit": "%", "date_range": "Aug 2026" },
  "correlation_changes": [
    { "asset_pair": "Energy-Technology",     "current": -0.03, "previous": 0.24 },
    { "asset_pair": "Financials-Technology", "current":  0.13, "previous": 0.26 }
  ],
  "rolling_returns": { "3mo": 1.8, "6mo": -10.1, "12mo": -17.5, "unit": "%" }
}
```

Each run writes a traceable pair into `reports/` — `report_Q3_2026.md` (narrative,
provenance block, and the metrics it came from) alongside `metrics_Q3_2026.json` (the
exact input). Any figure that reaches a slide can be walked back to the dict that
produced it.

## Setup

### Install
```bash
pip install -r requirements.txt
```

### Provide an API key

The narrative layer runs on either **Gemini** or **Claude**, whichever key it finds.
Put the key in a local `.env` (git-ignored):

```bash
echo 'GEMINI_API_KEY=your-key-here' > .env
```

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini backend (default) — `gemini-2.5-flash` |
| `ANTHROPIC_API_KEY` | Claude backend — `claude-sonnet-4-6` |
| `NARRATIVE_PROVIDER` | Force a backend: `gemini` or `anthropic` |
| `NARRATIVE_MODEL` | Override the model id |
| `PORTFOLIO_DSN` | Read `vw_Portfolio_Analytics` from PostgreSQL instead of the CSV |

The model backend sits behind a single `complete(system, user)` call in
`llm_client.py`. The grounding and validation logic is provider-independent — it is a
property of the system, not of the model.

### Generate a report

```bash
python 6_generate_narrative_report.py              # latest quarter
python 6_generate_narrative_report.py "Q2 2026"    # a specific quarter
python 6_generate_narrative_report.py --sample     # no price file needed
```

Prints the narrative, the validation verdict, and a whitespace-collapsed version ready
to paste into a Power BI text box. Exits non-zero if the narrative was flagged, so it
can gate a pipeline.

### Reproducing the validation

```bash
python 7_validation_suite.py
```

Generates a narrative for every available quarter, validates each, and prints the
measured pass rate. Full per-quarter results — every number found, every number
flagged, and the narrative text — are written to `reports/validation_results.json`.

## Design notes

- **Equal weighting.** The schema stores assets but no weights, so the portfolio is
  equal-weighted across the three equity holdings, with `^NSEI` held out as the
  benchmark. Both are constants at the top of `metrics_collector.py`.
- **Quarter-local drawdown.** Max drawdown is measured against the running peak
  *within* the quarter, so each quarter's figure stands alone rather than inheriting a
  peak set years earlier.
- **Prompt versioning.** `narrative_prompt.py` keeps the prompt separate from the
  generation code and logs `v1` (spec baseline) and `v2` (current) so a before/after
  comparison is a one-line change.
- **Determinism.** Temperature is 0.2 and the metrics JSON is serialized with sorted
  keys — commentary on a fixed set of numbers should be reproducible, and stable
  serialization keeps prompt caching effective on the Claude backend.
