# Phase 3 — Power BI: DAX Measures & Dashboard Layout Guide

## A. Connection Setup

1. Open Power BI Desktop.
2. **Get Data → PostgreSQL Database**.
3. Server: `localhost` (or your host), Database: `<your_db_name>`.
4. Import **only** the view: `vw_Portfolio_Analytics`.
5. Rename the imported table to `PortfolioAnalytics` (for clean DAX references).

---

## B. DAX Measures (exact formulas — mandatory)

Paste each measure into **Modeling → New Measure**.

---

### 1. Annualized Volatility

```dax
Annualized_Volatility =
STDEV.S( 'PortfolioAnalytics'[Daily_Return] ) * SQRT( 252 )
```

> Uses `STDEV.S` (sample standard deviation) scaled by √252 trading days.

---

### 2. Annualized Return (CAGR)

```dax
Annualized_Return =
VAR StartDate =
    CALCULATE(
        MIN( 'PortfolioAnalytics'[Date] ),
        ALLSELECTED( 'PortfolioAnalytics' )
    )
VAR EndDate =
    CALCULATE(
        MAX( 'PortfolioAnalytics'[Date] ),
        ALLSELECTED( 'PortfolioAnalytics' )
    )
VAR StartPrice =
    CALCULATE(
        MIN( 'PortfolioAnalytics'[Adj_Close] ),
        'PortfolioAnalytics'[Date] = StartDate
    )
VAR EndPrice =
    CALCULATE(
        MAX( 'PortfolioAnalytics'[Adj_Close] ),
        'PortfolioAnalytics'[Date] = EndDate
    )
VAR Years =
    DATEDIFF( StartDate, EndDate, DAY ) / 365.25
RETURN
    ( EndPrice / StartPrice ) ^ ( 1 / Years ) - 1
```

> Implements the CAGR formula `(End/Start)^(1/Years) - 1`.  
> Uses `CALCULATE`, `MIN`, `MAX`, and `DATEDIFF` as required.

---

### 3. Sharpe Ratio

```dax
Sharpe_Ratio =
DIVIDE(
    [Annualized_Return] - 0.05,
    [Annualized_Volatility]
)
```

> Risk-free rate assumed at 5% (0.05) per spec. `DIVIDE` handles zero-denominator safely.

---

### 4. Max Drawdown

```dax
Max_Drawdown =
MIN( 'PortfolioAnalytics'[Drawdown_Percentage] )
```

> Drawdown values are negative; MIN finds the worst (deepest) drawdown.

---

## C. Dashboard Layout

### Page 1 — Executive Summary

| Visual | Configuration |
|--------|--------------|
| **KPI Card 1** | Value: `[Annualized_Return]`, Format: Percentage, 2 dp |
| **KPI Card 2** | Value: `[Annualized_Volatility]`, Format: Percentage, 2 dp |
| **KPI Card 3** | Value: `[Sharpe_Ratio]`, Format: Decimal, 2 dp |
| **KPI Card 4** | Value: `[Max_Drawdown]`, Format: Percentage, 2 dp |
| **Line Chart** | X-axis: `Date`, Y-axis: `Cumulative_Growth`, Legend: `Asset_Symbol` |

**Line Chart tips:**
- Set Y-axis title to *"Cumulative Growth (1 = Starting Value)"*.
- Enable markers for each asset line.
- Apply a slicer on `Asset_Symbol` so analysts can isolate individual assets.

---

### Page 2 — Risk-Return Matrix

| Visual | Configuration |
|--------|--------------|
| **Scatter Chart** | X-axis: `[Annualized_Volatility]`, Y-axis: `[Annualized_Return]`, Values: `Asset_Symbol` |
| **Reference Lines** | Analytics Pane → add **Average Line** on both X and Y axes (dynamic) |
| **Clustered Bar Chart** | Axis: `Asset_Symbol`, Values: `[Sharpe_Ratio]` |

**Sharpe Ratio conditional formatting (bar chart):**
1. Select bar chart → Format → Data colors → **Conditional formatting → Field value / Rules**.
2. Rule 1: If value **≥ 1** → Color `#1E8449` (green).
3. Rule 2: If value **< 1** → Color `#C0392B` (red).

---

### Page 3 — Asset Correlation

| Visual | Configuration |
|--------|--------------|
| **Matrix Visual** | Rows: `Asset_Symbol`, Columns: `Asset_Symbol`, Values: Correlation measure (see below) |

#### Correlation DAX Measure

Because native Power BI does not have a built-in cross-asset correlation in a matrix context,
use the following measure. It computes the Pearson correlation between daily returns of the
**row** asset and **column** asset dynamically via DAX:

```dax
Correlation_Coefficient =
VAR RowAsset    = SELECTEDVALUE( 'PortfolioAnalytics'[Asset_Symbol] )
VAR ColAsset    = SELECTEDVALUE( 'PortfolioAnalytics'[Asset_Symbol] )   -- column context

-- Pull return series for both assets using the cross-filtered row/column context
VAR tblRow =
    CALCULATETABLE(
        SELECTCOLUMNS(
            'PortfolioAnalytics',
            "Date",         [Date],
            "Return_Row",   [Daily_Return]
        ),
        'PortfolioAnalytics'[Asset_Symbol] = RowAsset
    )

VAR tblCol =
    CALCULATETABLE(
        SELECTCOLUMNS(
            'PortfolioAnalytics',
            "Date",         [Date],
            "Return_Col",   [Daily_Return]
        ),
        'PortfolioAnalytics'[Asset_Symbol] = ColAsset
    )

-- Join on Date, then compute Pearson r
VAR tblJoined =
    NATURALLEFTOUTERJOIN( tblRow, tblCol )

VAR N    = COUNTROWS( tblJoined )
VAR SumX = SUMX( tblJoined, [Return_Row] )
VAR SumY = SUMX( tblJoined, [Return_Col] )
VAR SumXY= SUMX( tblJoined, [Return_Row] * [Return_Col] )
VAR SumX2= SUMX( tblJoined, [Return_Row] ^ 2 )
VAR SumY2= SUMX( tblJoined, [Return_Col] ^ 2 )

RETURN
DIVIDE(
    N * SumXY - SumX * SumY,
    SQRT(
        ( N * SumX2 - SumX ^ 2 ) * ( N * SumY2 - SumY ^ 2 )
    )
)
```

**Heatmap conditional formatting for Matrix:**
1. Select Matrix → Format → Cell elements → Background color → **Conditional formatting → Color scale**.
2. **Diverging scale:**
   - Minimum value (`-1`): `#1A5276` (Dark Red / Negative) ← Red end
   - Center value (`0`):   `#FFFFFF` (White / Neutral)
   - Maximum value (`+1`): `#154360` (Dark Blue / Positive)

> **Note:** Power BI uses the terms "Minimum/Center/Maximum" in the color scale dialog.  
> Per spec: Dark Blue = positive correlation, White = neutral, Dark Red = negative.

---

## D. Final Checklist

- [ ] PostgreSQL view `vw_Portfolio_Analytics` returns data without errors
- [ ] Power BI connected to PostgreSQL via native connector
- [ ] All 4 DAX measures created and formatted correctly
- [ ] Page 1: 4 KPI cards + Line chart with legend
- [ ] Page 2: Scatter chart with average reference lines + Conditional bar chart
- [ ] Page 3: Matrix visual with Pearson correlation heatmap

