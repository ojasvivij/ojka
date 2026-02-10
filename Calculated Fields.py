#!/usr/bin/env python
# coding: utf-8

# In[25]:


import duckdb

DB_PATH = "data/market_data.duckdb"
con = duckdb.connect(DB_PATH)


# In[2]:


con.execute("""
CREATE OR REPLACE VIEW income_statement_calculated AS
SELECT
    fi.*,

    -- EBIT (calculated)
    CASE
        WHEN sm.industry = 'Financials' THEN fi.operating_profit - fi.depreciation
        ELSE fi.ebitda - fi.depreciation
    END AS ebit,


    -- Shares Outstanding (FIXED UNITS)
    CASE
        WHEN fi.eps IS NOT NULL AND fi.eps != 0
        THEN (COALESCE(fi.net_income_adj, 0) * 1e7) / fi.eps
        ELSE NULL
    END AS shares_outstanding

FROM financial_income_statement fi
JOIN stocks_master sm USING (stock_id)
""")

print("✅ income_statement_calculated created")


# In[3]:


con.execute("""
SELECT
    sm.symbol,
    period_end,
    ROUND(shares_outstanding / 1e7, 2) AS shares_outstanding_crore
FROM income_statement_calculated i
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol = 'RELIANCE'
ORDER BY period_end DESC
LIMIT 3;
""").df()


# In[4]:


con.execute("""
CREATE OR REPLACE VIEW quarterly_results_calculated AS
SELECT
    fq.*,

    -- EBIT (calculated)
    CASE
        WHEN sm.industry = 'Financials' THEN fq.operating_profit - fq.depreciation
        ELSE fq.ebitda - fq.depreciation
    END AS ebit,



    -- Shares Outstanding (derived from EPS)
    CASE
        WHEN fq.eps IS NOT NULL AND fq.eps != 0
        THEN COALESCE(fq.net_income_adj, 0) / fq.eps
        ELSE NULL
    END AS shares_outstanding

FROM financial_quarterly_results fq
JOIN stocks_master sm USING (stock_id)
""")

print("✅ quarterly_results_calculated created")


# In[5]:


con.execute("""
CREATE OR REPLACE VIEW balance_sheet_calculated AS
SELECT
    fb.*,

    -- Total Equity
    COALESCE(equity_share_capital, 0)
  + COALESCE(equity_reserves, 0)
    AS total_equity,

    -- Total Liabilities
    COALESCE(total_assets, 0)
  - (COALESCE(equity_share_capital, 0) + COALESCE(equity_reserves, 0))
    AS total_liabilities,

    -- Net Fixed Assets
    (
    COALESCE(fb.fixed_assets, 0)
  - COALESCE(fb.accumulated_depreciation, 0)
    )
    AS net_fixed_assets,

    -- Total Debt
    COALESCE(fb.borrowings, 0)

    AS total_debt,

    -- Net Debt
    (
    COALESCE(fb.borrowings, 0)

    )
  - COALESCE(fb.cash_and_equivalents, 0)
    AS net_debt,

    -- Invested Capital
    (
    COALESCE(fb.equity_share_capital, 0)
  + COALESCE(fb.equity_reserves, 0)
    )
  + (
    COALESCE(fb.borrowings, 0)

  - COALESCE(fb.cash_and_equivalents, 0)
    )
    AS invested_capital,


    -- Net Borrowing
    (
        COALESCE(borrowings, 0)
   
    )
  -
    LAG(
        COALESCE(borrowings, 0)
   
    ) OVER (
        PARTITION BY stock_id
        ORDER BY period_end
    )
    AS net_borrowing_bs










FROM financial_balance_sheet fb
""")

print("✅ balance_sheet_calculated created")








# In[6]:


con.execute("""
CREATE OR REPLACE VIEW shareholding_pattern_calculated AS
SELECT
    sp.*,

    -- Institutional Holdings = FIIs + DIIs
    COALESCE(sp.fii_holding, 0)
  + COALESCE(sp.dii_holding, 0)
    AS institutional_holding

FROM shareholding_pattern sp
""")

print("✅ shareholding_pattern_calculated created")


# In[7]:


con.execute("""
CREATE OR REPLACE VIEW cashflow_calculated AS
SELECT
    fc.*,

    -- CAPEX
    COALESCE(fc.fixed_assets_purchased, 0)
  + COALESCE(fc.fixed_assets_sold, 0)
    AS capex

    

FROM financial_cashflow fc
""")

print("✅ cashflow_calculated created")


# In[29]:


con.execute("""
SELECT
    sm.symbol,
    *

FROM  income_statement_calculated
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol = 'RELIANCE'
ORDER BY period_end DESC
LIMIT 3;
""").df()


# In[28]:


con.execute("""
SELECT
    sm.symbol,
    *

FROM cashflow_calculated 
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol = 'RELIANCE'
ORDER BY period_end DESC
LIMIT 3;
""").df()


# In[8]:


con.execute("""
CREATE OR REPLACE VIEW income_statement_annual_growth AS
SELECT
    isc.stock_id,
    isc.period_end,

    isc.revenue,
    isc.net_income_adj,
    isc.eps,

    -- Revenue YoY Growth
    (isc.revenue
     - LAG(isc.revenue) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end))
    / NULLIF(LAG(isc.revenue) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end), 0)
        AS revenue_yoy_growth,

    -- Net Income YoY Growth
    (isc.net_income
     - LAG(isc.net_income_adj) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end))
    / NULLIF(LAG(isc.net_income_adj) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end), 0)
        AS profit_yoy_growth,

    -- EPS YoY Growth
    (isc.eps
     - LAG(isc.eps) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end))
    / NULLIF(LAG(isc.eps) OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end), 0)
        AS eps_yoy_growth

FROM income_statement_calculated isc
""")

print("✅ income_statement_annual_growth created")


# In[ ]:





# In[9]:


#ANNUAL YoY GROWTH VIEW


# In[10]:


con.execute("""
CREATE OR REPLACE VIEW income_statement_quarterly_qoq_growth AS
SELECT
    fq.stock_id,
    fq.period_end,

    fq.revenue,
    fq.net_income_adj,
    fq.eps,

    -- Revenue QoQ Growth
    (fq.revenue
     - LAG(fq.revenue) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.revenue) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS revenue_qoq_growth,

    -- Net Income QoQ Growth
    (fq.net_income
     - LAG(fq.net_income_adj) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.net_income_adj) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS profit_qoq_growth,

    -- EPS QoQ Growth
    (fq.eps
     - LAG(fq.eps) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.eps) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS eps_qoq_growth

FROM financial_quarterly_results fq
""")

print("✅ income_statement_quarterly_qoq_growth created")


# In[11]:


#QUARTERLY QoQ GROWTH


# In[12]:


#QUARTERLY YoY GROWTH (Seasonality-safe)


# In[13]:


con.execute("""
CREATE OR REPLACE VIEW income_statement_quarterly_yoy_growth AS
SELECT
    fq.stock_id,
    fq.period_end,

    fq.revenue,
    fq.net_income_adj,
    fq.eps,

    -- Revenue YoY Growth (Quarterly)
    (fq.revenue
     - LAG(fq.revenue, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.revenue, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS revenue_yoy_growth,

    -- Net Income YoY Growth (Quarterly)
    (fq.net_income
     - LAG(fq.net_income_adj, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.net_income_adj, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS profit_yoy_growth,

    -- EPS YoY Growth (Quarterly)
    (fq.eps
     - LAG(fq.eps, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end))
    / NULLIF(LAG(fq.eps, 4) OVER (PARTITION BY fq.stock_id ORDER BY fq.period_end), 0)
        AS eps_yoy_growth

FROM financial_quarterly_results fq
""")

print("✅ income_statement_quarterly_yoy_growth created")


# In[14]:


#✅ ANNUAL 3Y & 5Y CAGR VIEW


# In[15]:


con.execute("""
CREATE OR REPLACE VIEW income_statement_annual_cagr AS
SELECT
    isc.stock_id,
    isc.period_end,

    isc.revenue,
    isc.net_income_adj,
    isc.eps,

    /* =========================
       3Y CAGR
       ========================= */

    CASE
        WHEN isc.revenue > 0
         AND LAG(isc.revenue, 3) OVER w > 0
        THEN
            POWER(
                isc.revenue
                / LAG(isc.revenue, 3) OVER w,
                1.0 / 3
            ) - 1
        ELSE NULL
    END AS revenue_cagr_3y,

    CASE
        WHEN isc.net_income > 0
         AND LAG(isc.net_income_adj, 3) OVER w > 0
        THEN
            POWER(
                isc.net_income
                / LAG(isc.net_income_adj, 3) OVER w,
                1.0 / 3
            ) - 1
        ELSE NULL
    END AS profit_cagr_3y,

    CASE
        WHEN isc.eps > 0
         AND LAG(isc.eps, 3) OVER w > 0
        THEN
            POWER(
                isc.eps
                / LAG(isc.eps, 3) OVER w,
                1.0 / 3
            ) - 1
        ELSE NULL
    END AS eps_cagr_3y,

    /* =========================
       5Y CAGR
       ========================= */

    CASE
        WHEN isc.revenue > 0
         AND LAG(isc.revenue, 5) OVER w > 0
        THEN
            POWER(
                isc.revenue
                / LAG(isc.revenue, 5) OVER w,
                1.0 / 5
            ) - 1
        ELSE NULL
    END AS revenue_cagr_5y,

    CASE
        WHEN isc.net_income > 0
         AND LAG(isc.net_income_adj, 5) OVER w > 0
        THEN
            POWER(
                isc.net_income
                / LAG(isc.net_income_adj, 5) OVER w,
                1.0 / 5
            ) - 1
        ELSE NULL
    END AS profit_cagr_5y,

    CASE
        WHEN isc.eps > 0
         AND LAG(isc.eps, 5) OVER w > 0
        THEN
            POWER(
                isc.eps
                / LAG(isc.eps, 5) OVER w,
                1.0 / 5
            ) - 1
        ELSE NULL
    END AS eps_cagr_5y

FROM income_statement_calculated isc

WINDOW w AS (
    PARTITION BY isc.stock_id
    ORDER BY isc.period_end
)
""")

print("✅ income_statement_annual_cagr created (3Y & 5Y)")


# In[16]:


#✅ GROWTH CONSISTENCY SCORE — FINAL CODEx`


# In[17]:


con.execute("""
CREATE OR REPLACE VIEW growth_consistency_score AS
WITH base AS (
    SELECT
        stock_id,
        revenue_yoy_growth
    FROM income_statement_annual_growth
    WHERE revenue_yoy_growth IS NOT NULL
),

aggregates AS (
    SELECT
        stock_id,

        COUNT(*) AS total_years,

        -- Part A: Positive growth years
        SUM(
            CASE
                WHEN revenue_yoy_growth > 0 THEN 1
                ELSE 0
            END
        ) AS positive_years,

        -- Part B: Volatility (std dev of growth)
        STDDEV_SAMP(revenue_yoy_growth) AS growth_volatility

    FROM base
    GROUP BY stock_id
)

SELECT
    a.stock_id,

    a.total_years,
    a.positive_years,

    -- Positive Year Ratio
    CASE
        WHEN a.total_years > 0
        THEN a.positive_years * 1.0 / a.total_years
        ELSE NULL
    END AS positive_year_ratio,

    -- Volatility Penalty
    a.growth_volatility,

    -- Final Growth Consistency Score
    CASE
        WHEN a.total_years > 0
        THEN
            (a.positive_years * 1.0 / a.total_years)
            * (1.0 / (1.0 + COALESCE(a.growth_volatility, 0)))
        ELSE NULL
    END AS growth_consistency_score

FROM aggregates a
""")

print("✅ growth_consistency_score created")


# In[ ]:





# In[ ]:





# In[18]:


#✅ FINANCIAL RATIOS — FINAL CALCULATED VIEW


# In[19]:


con.execute("""
CREATE OR REPLACE VIEW financial_ratios_calculated AS
SELECT
    isc.stock_id,
    isc.period_end,

    /* =========================
       LEVERAGE RATIOS
       ========================= */

    -- Debt to Equity
    CASE
        WHEN bsc.total_equity != 0
        THEN bsc.total_debt / bsc.total_equity
        ELSE NULL
    END AS debt_to_equity,

    -- Debt Ratio
    CASE
        WHEN bsc.total_assets != 0
        THEN bsc.total_debt / bsc.total_assets
        ELSE NULL
    END AS debt_ratio,

    /* =========================
       COVERAGE RATIO
       ========================= */

    -- Interest Coverage Ratio
    CASE
        WHEN isc.interest_expense IS NOT NULL
         AND isc.interest_expense != 0
        THEN isc.ebit / isc.interest_expense
        ELSE NULL
    END AS interest_coverage_ratio,

    /* =========================
       MARGINS
       ========================= */

    -- EBITDA Margin
    CASE
        WHEN isc.revenue != 0
        THEN isc.ebitda / isc.revenue
        ELSE NULL
    END AS ebitda_margin,

    -- EBIT Margin
    CASE
        WHEN isc.revenue != 0
        THEN isc.ebit / isc.revenue
        ELSE NULL
    END AS ebit_margin,

    -- EBT Margin
    CASE
        WHEN isc.revenue != 0
        THEN isc.ebt / isc.revenue
        ELSE NULL
    END AS ebt_margin,

    -- Net Income Margin (Adjusted)
    CASE
        WHEN isc.revenue != 0
        THEN isc.net_income_adj / isc.revenue
        ELSE NULL
    END AS net_income_margin,

    /* =========================
       RETURN RATIOS
       ========================= */

    -- Return on Equity (ROE)
    CASE
        WHEN bsc.total_equity != 0
        THEN isc.net_income / bsc.total_equity
        ELSE NULL
    END AS return_on_equity,

    -- Return on Invested Capital (ROIC)
    CASE
        WHEN bsc.invested_capital != 0
        THEN
            (
                isc.ebit
                * (1 - COALESCE(isc.tax_expense_percent, 0) / 100.0)
            ) / bsc.invested_capital
        ELSE NULL
    END AS return_on_invested_capital,

    -- Return on Assets (ROA)
    CASE
        WHEN bsc.total_assets != 0
        THEN isc.net_income / bsc.total_assets
        ELSE NULL
    END AS return_on_assets,

    /* =========================
       EFFICIENCY RATIOS
       ========================= */

    -- Asset Turnover
    CASE
        WHEN bsc.total_assets != 0
        THEN isc.revenue / bsc.total_assets
        ELSE NULL
    END AS asset_turnover,

    -- Receivables Turnover
    CASE
        WHEN bsc.trade_receivables IS NOT NULL
         AND bsc.trade_receivables != 0
        THEN isc.revenue / bsc.trade_receivables
        ELSE NULL
    END AS receivables_turnover

FROM income_statement_calculated isc
JOIN balance_sheet_calculated bsc
  ON isc.stock_id = bsc.stock_id
 AND isc.period_end = bsc.period_end
JOIN stocks_master sm
  ON isc.stock_id = sm.stock_id
""")

print("✅ financial_ratios_calculated created")


# In[ ]:





# In[ ]:





# In[20]:


con.execute("""
CREATE OR REPLACE VIEW financial_ratios_3y_5y_avg AS
SELECT
    fr.stock_id,
    fr.period_end,

    /* =========================
       LEVERAGE RATIOS
       ========================= */

    AVG(fr.debt_to_equity) OVER w3 AS debt_to_equity_3y_avg,
    AVG(fr.debt_to_equity) OVER w5 AS debt_to_equity_5y_avg,

    AVG(fr.debt_ratio) OVER w3 AS debt_ratio_3y_avg,
    AVG(fr.debt_ratio) OVER w5 AS debt_ratio_5y_avg,

    /* =========================
       COVERAGE
       ========================= */

    AVG(fr.interest_coverage_ratio) OVER w3 AS interest_coverage_3y_avg,
    AVG(fr.interest_coverage_ratio) OVER w5 AS interest_coverage_5y_avg,

    /* =========================
       MARGINS
       ========================= */

    AVG(fr.ebitda_margin) OVER w3 AS ebitda_margin_3y_avg,
    AVG(fr.ebitda_margin) OVER w5 AS ebitda_margin_5y_avg,

    AVG(fr.ebit_margin) OVER w3 AS ebit_margin_3y_avg,
    AVG(fr.ebit_margin) OVER w5 AS ebit_margin_5y_avg,

    AVG(fr.ebt_margin) OVER w3 AS ebt_margin_3y_avg,
    AVG(fr.ebt_margin) OVER w5 AS ebt_margin_5y_avg,

    AVG(fr.net_income_margin) OVER w3 AS net_income_margin_3y_avg,
    AVG(fr.net_income_margin) OVER w5 AS net_income_margin_5y_avg,

    /* =========================
       RETURN RATIOS
       ========================= */

    AVG(fr.return_on_equity) OVER w3 AS roe_3y_avg,
    AVG(fr.return_on_equity) OVER w5 AS roe_5y_avg,

    AVG(fr.return_on_invested_capital) OVER w3 AS roic_3y_avg,
    AVG(fr.return_on_invested_capital) OVER w5 AS roic_5y_avg,

    AVG(fr.return_on_assets) OVER w3 AS roa_3y_avg,
    AVG(fr.return_on_assets) OVER w5 AS roa_5y_avg,

    /* =========================
       EFFICIENCY
       ========================= */

    AVG(fr.asset_turnover) OVER w3 AS asset_turnover_3y_avg,
    AVG(fr.asset_turnover) OVER w5 AS asset_turnover_5y_avg,

    AVG(fr.receivables_turnover) OVER w3 AS receivables_turnover_3y_avg,
    AVG(fr.receivables_turnover) OVER w5 AS receivables_turnover_5y_avg

FROM financial_ratios_calculated fr

WINDOW
    w3 AS (
        PARTITION BY fr.stock_id
        ORDER BY fr.period_end
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ),
    w5 AS (
        PARTITION BY fr.stock_id
        ORDER BY fr.period_end
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    )
""")

print("✅ financial_ratios_3y_5y_avg created")


# In[21]:


con.execute("""
SELECT
 *
FROM  financial_ratios_3y_5y_avg fi
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol = 'RELIANCE'

LIMIT 20
""").df()


# In[30]:


con.close()

