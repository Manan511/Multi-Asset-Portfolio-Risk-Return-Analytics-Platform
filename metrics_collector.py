"""
Metrics Collector — bridge between the existing analytics pipeline and the AI layer
Multi-Asset Portfolio Risk & Return Analytics Platform

This module does NOT define any new analytics. Every formula below is a 1:1
restatement of a formula that already exists in this project:

    Daily_Return          -> 3_analytical_view.sql, CTE 2 (LAG)
    Running_Peak          -> 3_analytical_view.sql, CTE 3 (MAX OVER)
    Drawdown_Percentage   -> 3_analytical_view.sql, CTE 4
    Annualized_Volatility -> 4_powerbi_dax_measures.md, measure 1 (STDEV.S * SQRT(252))
    Annualized_Return     -> 4_powerbi_dax_measures.md, measure 2 (CAGR, /365.25)
    Sharpe_Ratio          -> 4_powerbi_dax_measures.md, measure 3 (rf = 0.05)
    Max_Drawdown          -> 4_powerbi_dax_measures.md, measure 4 (MIN of drawdown)
    Correlation           -> 4_powerbi_dax_measures.md, Correlation_Coefficient (Pearson)

Its only job is to take those already-defined quantities and serialize them into
the flat `metrics_summary` dict that narrative_generator.py narrates. Keeping the
serialization here is what lets the AI layer stay a pure narrator: it never sees
a price series and has nothing to recompute.

Source of truth for prices is `portfolio_raw_data.csv` (output of
1_data_extraction.py). Set PORTFOLIO_DSN to read `vw_Portfolio_Analytics`
straight out of PostgreSQL instead.
"""

import math
import os

import pandas as pd


# ── Configuration (mirrors the existing pipeline's assumptions) ──────────────

RISK_FREE_RATE   = 0.05    # same 5% assumed by the Sharpe_Ratio DAX measure
TRADING_DAYS     = 252     # same annualization factor as Annualized_Volatility
BENCHMARK_SYMBOL = '^NSEI'  # index, held out of the portfolio itself

# Equal weights across the three equity holdings. The existing pipeline tracks
# assets but stores no weights, so equal-weighting is stated explicitly here
# rather than assumed silently. Change these to match a real book.
PORTFOLIO_WEIGHTS = {
    'RELIANCE.NS': 1 / 3,
    'HDFCBANK.NS': 1 / 3,
    'TCS.NS':      1 / 3,
}

# Human-readable labels used in the correlation pairs the narrative talks about.
ASSET_LABELS = {
    'RELIANCE.NS': 'Energy',
    'HDFCBANK.NS': 'Financials',
    'TCS.NS':      'Technology',
    '^NSEI':       'NIFTY 50',
}

CSV_FILE = 'portfolio_raw_data.csv'


# ── Loading ──────────────────────────────────────────────────────────────────

def load_price_panel(csv_file: str = CSV_FILE) -> pd.DataFrame:
    """Return a wide Date x Asset_Symbol frame of Adj_Close.

    Reads PostgreSQL if PORTFOLIO_DSN is set, otherwise the CSV that
    1_data_extraction.py writes.
    """
    dsn = os.environ.get('PORTFOLIO_DSN')

    if dsn:
        import psycopg2
        with psycopg2.connect(dsn) as conn:
            tall = pd.read_sql(
                'SELECT Date, Asset_Symbol, Adj_Close FROM vw_Portfolio_Analytics',
                conn,
            )
    else:
        tall = pd.read_csv(csv_file)

    tall.columns = [c.lower() for c in tall.columns]
    tall['date'] = pd.to_datetime(tall['date'])

    panel = tall.pivot(index='date', columns='asset_symbol', values='adj_close')
    return panel.sort_index()


# ── Pipeline formulas, restated ──────────────────────────────────────────────

def daily_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Daily_Return — CTE 2 of 3_analytical_view.sql, vectorised.

    fill_method=None mirrors LAG's behaviour: a gap in one asset's series yields
    a null return for that day rather than a stale carried-forward price.
    """
    return panel.pct_change(fill_method=None)


def portfolio_return_series(returns: pd.DataFrame) -> pd.Series:
    """Weighted daily return of the holdings (the benchmark is excluded)."""
    held = [s for s in PORTFOLIO_WEIGHTS if s in returns.columns]
    weights = pd.Series({s: PORTFOLIO_WEIGHTS[s] for s in held})
    return (returns[held] * weights).sum(axis=1, min_count=len(held))


def annualized_volatility(rets: pd.Series) -> float:
    """Annualized_Volatility — STDEV.S(Daily_Return) * SQRT(252)."""
    return float(rets.std(ddof=1) * math.sqrt(TRADING_DAYS))


def annualized_return(index_level: pd.Series) -> float:
    """Annualized_Return — (End/Start)^(1/Years) - 1, Years = days / 365.25."""
    start_price, end_price = float(index_level.iloc[0]), float(index_level.iloc[-1])
    years = (index_level.index[-1] - index_level.index[0]).days / 365.25
    if years <= 0 or start_price <= 0:
        return float('nan')
    return (end_price / start_price) ** (1 / years) - 1


def sharpe_ratio(ann_return: float, ann_vol: float) -> float:
    """Sharpe_Ratio — DIVIDE(Annualized_Return - 0.05, Annualized_Volatility)."""
    if ann_vol == 0 or math.isnan(ann_vol):
        return float('nan')
    return (ann_return - RISK_FREE_RATE) / ann_vol


def max_drawdown(index_level: pd.Series) -> tuple:
    """Max_Drawdown — MIN((Adj_Close - Running_Peak) / Running_Peak).

    Returns (worst drawdown as a negative fraction, date it occurred).
    """
    running_peak = index_level.cummax()
    drawdown = (index_level - running_peak) / running_peak
    return float(drawdown.min()), drawdown.idxmin()


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Correlation_Coefficient — pairwise Pearson r on daily returns."""
    return returns.corr(method='pearson')


# ── Quarter assembly ─────────────────────────────────────────────────────────

def _quarter_label(period) -> str:
    return f'Q{period.quarter} {period.year}'


def _pct(x, dp: int = 1):
    """Round to a percentage figure, or None when the input is unusable.

    Whatever this returns is exactly what the model is allowed to say — the
    traceability validator matches the narrative's digits against these values.
    """
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(x * 100, dp)


def _num(x, dp: int = 2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), dp)


def _rolling_return(index_level: pd.Series, as_of, months: int):
    """Simple total return over the trailing N months ending at `as_of`."""
    start = as_of - pd.DateOffset(months=months)
    window = index_level.loc[(index_level.index > start) & (index_level.index <= as_of)]
    if len(window) < 2:
        return None
    return float(window.iloc[-1] / window.iloc[0] - 1)


def build_metrics_summary(panel: pd.DataFrame, quarter: pd.Period) -> dict:
    """Assemble one `metrics_summary` dict for a single quarter.

    Current-quarter figures come from that quarter's window; the "previous"
    figures come from the quarter immediately before it, so the narrative can
    talk about direction of travel.
    """
    returns   = daily_returns(panel)
    port_rets = portfolio_return_series(returns).dropna()

    # Cumulative growth of the portfolio — EXP(SUM(LN(1+r))) from CTE 4,
    # which is just the compounded product of (1 + daily return).
    port_level = (1 + port_rets).cumprod()

    prev_quarter = quarter - 1
    cur_mask  = port_rets.index.to_period('Q') == quarter
    prev_mask = port_rets.index.to_period('Q') == prev_quarter

    cur_rets, prev_rets = port_rets[cur_mask], port_rets[prev_mask]
    if len(cur_rets) < 2:
        raise ValueError(f'Not enough observations in {_quarter_label(quarter)}')

    cur_level = port_level[cur_mask]

    cur_vol  = annualized_volatility(cur_rets)
    prev_vol = annualized_volatility(prev_rets) if len(prev_rets) >= 2 else float('nan')

    cur_ann_ret  = annualized_return(cur_level)
    cur_sharpe   = sharpe_ratio(cur_ann_ret, cur_vol)
    if len(prev_rets) >= 2:
        prev_level  = port_level[prev_mask]
        prev_sharpe = sharpe_ratio(annualized_return(prev_level), prev_vol)
    else:
        prev_sharpe = float('nan')

    dd_value, dd_date = max_drawdown(cur_level)

    # Correlation changes: same Pearson r as the Power BI matrix, computed on the
    # quarter's daily returns and compared with the prior quarter's.
    held = [s for s in PORTFOLIO_WEIGHTS if s in returns.columns]
    cur_corr  = correlation_matrix(returns.loc[cur_rets.index, held])
    prev_corr = (correlation_matrix(returns.loc[prev_rets.index, held])
                 if len(prev_rets) >= 2 else None)

    correlation_changes = []
    for i, a in enumerate(held):
        for b in held[i + 1:]:
            cur_r = _num(cur_corr.loc[a, b])
            if cur_r is None:
                continue
            entry = {
                'asset_pair': f'{ASSET_LABELS.get(a, a)}-{ASSET_LABELS.get(b, b)}',
                'current': cur_r,
            }
            if prev_corr is not None:
                entry['previous'] = _num(prev_corr.loc[a, b])
            correlation_changes.append(entry)

    # Surface the two pairs that moved most — a narrative under 120 words cannot
    # carry every pair, and the biggest movers are what an analyst would cite.
    def _movement(e):
        if e.get('previous') is None:
            return 0.0
        return abs(e['current'] - e['previous'])

    correlation_changes.sort(key=_movement, reverse=True)
    correlation_changes = correlation_changes[:2]

    as_of = cur_level.index[-1]

    summary = {
        'period': _quarter_label(quarter),
        'previous_period': _quarter_label(prev_quarter),
        'volatility': {
            'current': _pct(cur_vol),
            'previous': _pct(prev_vol),
            'unit': '%',
            'basis': 'annualized',
        },
        'sharpe_ratio': {
            'current': _num(cur_sharpe),
            'previous': _num(prev_sharpe),
        },
        'max_drawdown': {
            'value': _pct(dd_value),
            'unit': '%',
            'date_range': dd_date.strftime('%b %Y'),
        },
        'correlation_changes': correlation_changes,
        'rolling_returns': {
            '3mo':  _pct(_rolling_return(port_level, as_of, 3)),
            '6mo':  _pct(_rolling_return(port_level, as_of, 6)),
            '12mo': _pct(_rolling_return(port_level, as_of, 12)),
            'unit': '%',
        },
    }

    # Drop keys whose value could not be computed, so the model is never handed
    # a null it might try to describe.
    return _prune_nulls(summary)


def _prune_nulls(obj):
    if isinstance(obj, dict):
        return {k: _prune_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune_nulls(v) for v in obj]
    return obj


def available_quarters(panel: pd.DataFrame, min_days: int = 40) -> list:
    """Quarters with enough observations to characterise, oldest first.

    The first and last quarters in the file are usually partial, so they are
    excluded by the min_days threshold rather than reported on thin data.
    """
    quarters = panel.index.to_period('Q')
    counts = pd.Series(1, index=quarters).groupby(level=0).sum()
    return [q for q, n in counts.items() if n >= min_days]


def collect_all(csv_file: str = CSV_FILE) -> list:
    """Every quarter's metrics_summary, oldest first."""
    panel = load_price_panel(csv_file)
    out = []
    for q in available_quarters(panel):
        try:
            out.append(build_metrics_summary(panel, q))
        except ValueError:
            continue
    return out


if __name__ == '__main__':
    import json
    for m in collect_all():
        print(json.dumps(m, indent=2, sort_keys=True))
        print('-' * 70)
