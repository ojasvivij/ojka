#!/usr/bin/env python
# coding: utf-8

# In[1]:


#CONNECT TO DATABASE


# In[129]:


import duckdb
import pandas as pd
from pathlib import Path

# DB path
DB_PATH = "data/market_data.duckdb"

# Connect
con = duckdb.connect(DB_PATH)

print("✅ Connected to DuckDB")


# In[3]:


#CLEAN RESET (DROP OLD OBJECTS SAFELY)


# In[4]:


import duckdb

DB_PATH = "data/market_data.duckdb"
con = duckdb.connect(DB_PATH)

# Objects we want to remove (name only, no type assumptions)
objects_to_drop = [
    "market_prices_daily",
    "stock_prices_daily",
    "market_returns_daily",
    "stock_returns_daily",
    "market_return_annualised_correct",
    "stock_return_annualised_correct",
    "beta_2y_calculated",
    "market_erp_correct",
    "cost_of_equity_latest",
]

# Drop TABLES if they exist
tables = set(
    con.execute("SELECT table_name FROM duckdb_tables()").fetchall()
)
tables = {t[0] for t in tables}

# Drop VIEWS if they exist
views = set(
    con.execute("SELECT view_name FROM duckdb_views()").fetchall()
)
views = {v[0] for v in views}

for obj in objects_to_drop:
    if obj in tables:
        con.execute(f"DROP TABLE {obj}")
        print(f"🗑️ Dropped TABLE: {obj}")
    elif obj in views:
        con.execute(f"DROP VIEW {obj}")
        print(f"🗑️ Dropped VIEW : {obj}")

print("✅ Database reset completed safely")


# In[5]:


#CLEAN RESET (DROP OLD OBJECTS SAFELY)


# In[6]:


BASE_PATH = Path(r"C:\Users\Ojasvi Vij\Documents\NIFTY500 Agent\data")

NIFTY_FILES = [
    BASE_PATH / "NIFTY 500-01-01-2023-to-31-12-2023.csv",
    BASE_PATH / "NIFTY 500-01-01-2024-to-31-12-2024.csv",
    BASE_PATH / "NIFTY 500-01-01-2025-to-31-12-2025.csv",
    BASE_PATH / "NIFTY 500-01-01-2026-to-07-02-2026.csv",
]

STOCK_PRICE_FILE = BASE_PATH / "data_daily.xlsx"


# In[7]:


#CELL 3 — LOAD NIFTY 500 DAILY PRICES


# In[8]:


dfs = []

for f in NIFTY_FILES:
    df = pd.read_csv(f)
    df.columns = df.columns.str.lower().str.strip()
    dfs.append(df)

nifty = pd.concat(dfs, ignore_index=True)

nifty = nifty.rename(columns={
    "date": "date",
    "close": "adj_close"
})

nifty["date"] = pd.to_datetime(nifty["date"])

con.execute("""
CREATE TABLE market_prices_daily (
    date DATE,
    adj_close DOUBLE
)
""")

con.register("nifty_df", nifty[["date", "adj_close"]])
con.execute("INSERT INTO market_prices_daily SELECT * FROM nifty_df")

print("✅ Market prices loaded")


# In[9]:


#CREATE MARKET DAILY RETURNS (LOG RETURNS)


# In[10]:


con.execute("""
CREATE VIEW market_returns_daily AS
SELECT
    date,
    LN(adj_close / LAG(adj_close) OVER (ORDER BY date)) AS market_return
FROM market_prices_daily
""")

print("✅ Market daily returns created")


# In[11]:


con.execute("SELECT * FROM market_returns_daily LIMIT 5").df()


# In[12]:


#CORRECT ANNUALISED MARKET RETURN (GEOMETRIC)


# In[13]:


con.execute("""
CREATE TABLE market_return_annualised_correct AS
SELECT
    MIN(date) AS start_date,
    MAX(date) AS end_date,

    EXP(SUM(market_return)) - 1 AS total_return,

    DATE_DIFF('day', MIN(date), MAX(date)) / 365.25 AS years,

    POWER(
        EXP(SUM(market_return)),
        1.0 / (DATE_DIFF('day', MIN(date), MAX(date)) / 365.25)
    ) - 1 AS annualised_return
FROM market_returns_daily
""")

print("✅ Annualised market return computed")


# In[14]:


con.execute("SELECT * FROM market_return_annualised_correct").df()


# In[15]:


#LOAD STOCK DAILY PRICES


# In[16]:


df = pd.read_excel(STOCK_PRICE_FILE)
df.columns = df.columns.str.lower().str.strip()

df = df.rename(columns={"close": "adj_close"})
df["date"] = pd.to_datetime(df["date"])

stock_map = dict(
    con.execute("SELECT symbol, stock_id FROM stocks_master").fetchall()
)

df["stock_id"] = df["symbol"].map(stock_map)
df = df.dropna(subset=["stock_id"])

con.execute("""
CREATE TABLE stock_prices_daily (
    stock_id INTEGER,
    date DATE,
    adj_close DOUBLE
)
""")

con.register("prices_df", df[["stock_id", "date", "adj_close"]])
con.execute("INSERT INTO stock_prices_daily SELECT * FROM prices_df")

print("✅ Stock prices loaded")


# In[17]:


#STOCK DAILY RETURNS (LOG RETURNS)


# In[18]:


con.execute("""
CREATE VIEW stock_returns_daily AS
SELECT
    stock_id,
    date,
    LN(adj_close / LAG(adj_close) OVER (
        PARTITION BY stock_id ORDER BY date
    )) AS stock_return
FROM stock_prices_daily
""")

print("✅ Stock daily returns created")


# In[19]:


#CORRECT ANNUALISED STOCK RETURNS


# In[20]:


con.execute("""
CREATE TABLE stock_return_annualised_correct AS
SELECT
    stock_id,

    MIN(date) AS start_date,
    MAX(date) AS end_date,

    EXP(SUM(stock_return)) - 1 AS total_return,

    DATE_DIFF('day', MIN(date), MAX(date)) / 365.25 AS years,

    POWER(
        EXP(SUM(stock_return)),
        1.0 / (DATE_DIFF('day', MIN(date), MAX(date)) / 365.25)
    ) - 1 AS annualised_return
FROM stock_returns_daily
GROUP BY stock_id
""")

print("✅ Annualised stock returns computed")


# In[21]:


#ROLLING BETA (2 YEARS ≈ 504 DAYS)


# In[22]:


con.execute("""
CREATE TABLE beta_2y_calculated AS
SELECT
    s.stock_id,
    s.date,

    COVAR_SAMP(s.stock_return, m.market_return)
        OVER w
    /
    VAR_SAMP(m.market_return)
        OVER w AS beta_2y
FROM stock_returns_daily s
JOIN market_returns_daily m USING (date)
WINDOW w AS (
    PARTITION BY s.stock_id
    ORDER BY s.date
    ROWS BETWEEN 503 PRECEDING AND CURRENT ROW
)
""")

print("✅ Rolling beta calculated")


# In[23]:


#COST OF EQUITY (USING REALISED ERP)


# In[24]:


RISK_FREE = 0.072

con.execute(f"""
CREATE TABLE cost_of_equity_latest AS
WITH erp AS (
    SELECT
        annualised_return - {RISK_FREE} AS equity_risk_premium
    FROM market_return_annualised_correct
)
SELECT
    b.stock_id,
    b.date,
    b.beta_2y,
    erp.equity_risk_premium,
    {RISK_FREE} + b.beta_2y * erp.equity_risk_premium AS cost_of_equity
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY stock_id
               ORDER BY date DESC
           ) AS rn
    FROM beta_2y_calculated
) b
CROSS JOIN erp
WHERE rn = 1
""")

print("✅ Cost of Equity (realised ERP) created")


# In[25]:


con.execute("""
SELECT
    sm.symbol,
    c.beta_2y,
    c.equity_risk_premium,
    c.cost_of_equity
FROM cost_of_equity_latest c
JOIN stocks_master sm USING (stock_id)
ORDER BY sm.symbol
LIMIT 20
""").df()


# In[26]:


con.execute("""
CREATE OR REPLACE VIEW vw_debt_march AS
SELECT
    stock_id,
    period_end,
    total_debt
FROM balance_sheet_calculated
WHERE EXTRACT(month FROM period_end) = 3;
""")


# In[27]:


con.execute("""
SELECT
    sm.symbol,
    d.period_end,
    d.total_debt
FROM vw_debt_march d
JOIN stocks_master sm
  ON d.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY d.period_end;
""").df()


# In[28]:


con.execute("""
CREATE OR REPLACE VIEW vw_interest_march AS
SELECT
    stock_id,
    period_end,
    interest_expense
FROM income_statement_calculated
WHERE EXTRACT(month FROM period_end) = 3;
""")


# In[29]:


con.execute("""
SELECT
    sm.symbol,
    i.period_end,
    i.interest_expense
FROM vw_interest_march i
JOIN stocks_master sm
  ON i.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY i.period_end;
""").df()


# In[30]:


con.execute("""
DROP TABLE IF EXISTS tbl_avg_debt;

CREATE TABLE tbl_avg_debt AS
SELECT
    stock_id,
    period_end,
    total_debt,
    (
        total_debt
      + LAG(total_debt) OVER (
            PARTITION BY stock_id
            ORDER BY period_end
        )
    ) / 2.0 AS avg_debt
FROM vw_debt_march;
""")


# In[31]:


con.execute("""
SELECT
    sm.symbol,
    d.period_end,
    d.total_debt,
    d.avg_debt
FROM tbl_avg_debt d
JOIN stocks_master sm
  ON d.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY d.period_end;
""").df()


# In[32]:


con.execute("""
DROP TABLE IF EXISTS tbl_cost_of_debt;

CREATE TABLE tbl_cost_of_debt AS
SELECT
    d.stock_id,
    d.period_end,
    d.avg_debt,
    i.interest_expense,
    CASE
        WHEN d.avg_debt IS NULL OR d.avg_debt = 0 THEN NULL
        ELSE i.interest_expense / d.avg_debt
    END AS cost_of_debt_pre_tax
FROM tbl_avg_debt d
LEFT JOIN vw_interest_march i
  ON d.stock_id = i.stock_id
 AND d.period_end = i.period_end;
""")


# In[33]:


con.execute("""
SELECT
    sm.symbol,
    c.period_end,
    c.avg_debt,
    c.interest_expense,
    ROUND(c.cost_of_debt_pre_tax * 100, 2) AS cost_of_debt_pct
FROM tbl_cost_of_debt c
JOIN stocks_master sm
  ON c.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY c.period_end;
""").df()


# In[34]:


con.execute("""
DROP TABLE IF EXISTS tbl_cost_of_debt_latest;

CREATE TABLE tbl_cost_of_debt_latest AS
SELECT *
FROM (
    SELECT
        stock_id,
        period_end,
        cost_of_debt_pre_tax,
        ROW_NUMBER() OVER (
            PARTITION BY stock_id
            ORDER BY period_end DESC
        ) AS rn
    FROM tbl_cost_of_debt
    WHERE cost_of_debt_pre_tax IS NOT NULL
) t
WHERE rn = 1;
""")


# In[35]:


con.execute("""
SELECT
    sm.symbol,
    l.period_end,
    ROUND(l.cost_of_debt_pre_tax * 100, 2) AS cost_of_debt_pct
FROM tbl_cost_of_debt_latest l
JOIN stocks_master sm
  ON l.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE';
""").df()


# In[36]:


#TOTAL EQUITY (SOURCE, NOT RECOMPUTED


# In[37]:


con.execute("""
CREATE OR REPLACE VIEW vw_equity_march AS
SELECT
    stock_id,
    period_end,
    total_equity
FROM balance_sheet_calculated
WHERE EXTRACT(month FROM period_end) = 3;
""")


# In[38]:


con.execute("""
SELECT
    sm.symbol,
    e.period_end,
    e.total_equity
FROM vw_equity_march e
JOIN stocks_master sm
  ON e.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY e.period_end;
""").df()


# In[39]:


#NET DEBT (SOURCE, NOT RECOMPUTED)


# In[40]:


con.execute("""
CREATE OR REPLACE VIEW vw_net_debt_march AS
SELECT
    stock_id,
    period_end,
    net_debt
FROM balance_sheet_calculated
WHERE EXTRACT(month FROM period_end) = 3;
""")


# In[41]:


con.execute("""
SELECT
    sm.symbol,
    n.period_end,
    n.net_debt
FROM vw_net_debt_march n
JOIN stocks_master sm
  ON n.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY n.period_end;
""").df()


# In[42]:


con.execute("""
DROP TABLE IF EXISTS tbl_capital_structure;

CREATE TABLE tbl_capital_structure AS
SELECT
    d.stock_id,
    d.period_end,
    d.total_debt,
    e.total_equity,

    (d.total_debt + e.total_equity) AS total_capital,

    CASE
        WHEN (d.total_debt + e.total_equity) = 0 THEN NULL
        ELSE d.total_debt / (d.total_debt + e.total_equity)
    END AS weight_debt,

    CASE
        WHEN (d.total_debt + e.total_equity) = 0 THEN NULL
        ELSE e.total_equity / (d.total_debt + e.total_equity)
    END AS weight_equity

FROM vw_debt_march d
JOIN vw_equity_march e
  ON d.stock_id = e.stock_id
 AND d.period_end = e.period_end;
""")


# In[43]:


con.execute("""
CREATE OR REPLACE VIEW vw_capital_structure AS
SELECT * FROM tbl_capital_structure;
""")


# In[44]:


con.execute("""
SELECT
    sm.symbol,
    c.period_end,
    c.total_debt,
    c.total_equity,
    ROUND(c.weight_debt * 100, 2)   AS weight_debt_pct,
    ROUND(c.weight_equity * 100, 2) AS weight_equity_pct
FROM vw_capital_structure c
JOIN stocks_master sm
  ON c.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE'
ORDER BY c.period_end;
""").df()


# In[45]:


con.execute("""
DROP TABLE IF EXISTS tbl_capital_structure_latest;

CREATE TABLE tbl_capital_structure_latest AS
SELECT *
FROM (
    SELECT
        stock_id,
        period_end,
        total_debt,
        total_equity,
        weight_debt,
        weight_equity,
        ROW_NUMBER() OVER (
            PARTITION BY stock_id
            ORDER BY period_end DESC
        ) AS rn
    FROM tbl_capital_structure
) t
WHERE rn = 1;
""")


# In[46]:


con.execute("""
SELECT
    sm.symbol,
    c.period_end,
    ROUND(c.weight_debt * 100, 2)   AS weight_debt_pct,
    ROUND(c.weight_equity * 100, 2) AS weight_equity_pct
FROM tbl_capital_structure_latest c
JOIN stocks_master sm
  ON c.stock_id = sm.stock_id
WHERE sm.symbol = 'RELIANCE';
""").df()


# In[47]:


TAX_RATE = 0.25

con.execute(f"""
DROP TABLE IF EXISTS tbl_wacc_latest;

CREATE TABLE tbl_wacc_latest AS
SELECT
    cs.stock_id,

    cs.period_end              AS capital_date,
    ce.date                    AS equity_date,

    cs.weight_equity,
    cs.weight_debt,

    ce.cost_of_equity,
    cd.cost_of_debt_pre_tax,

    -- WACC calculation
    (
        cs.weight_equity * ce.cost_of_equity
      + cs.weight_debt
        * cd.cost_of_debt_pre_tax
        * (1 - {TAX_RATE})
    ) AS wacc

FROM tbl_capital_structure_latest cs

LEFT JOIN cost_of_equity_latest ce
  ON cs.stock_id = ce.stock_id

LEFT JOIN tbl_cost_of_debt_latest cd
  ON cs.stock_id = cd.stock_id;
""")

print("✅ WACC (latest) created")


# In[48]:


con.execute("""
CREATE OR REPLACE VIEW vw_wacc_latest AS
SELECT * FROM tbl_wacc_latest;
""")


# In[659]:


con.execute("""
SELECT
    sm.symbol,

    ROUND(weight_equity * 100, 2) AS weight_equity_pct,
    ROUND(weight_debt * 100, 2)   AS weight_debt_pct,

    ROUND(cost_of_equity * 100, 2)        AS cost_of_equity_pct,
    ROUND(cost_of_debt_pre_tax * 100, 2)  AS cost_of_debt_pct,

    ROUND(wacc * 100, 2) AS wacc_pct
FROM vw_wacc_latest w
JOIN stocks_master sm
  ON w.stock_id = sm.stock_id
WHERE sm.symbol in ('RELIANCE','BEL','ASIANPAINT','*');
""").df()


# In[ ]:





# In[580]:


con.execute("""
-- FCFF & growth
DROP TABLE IF EXISTS tbl_fcff_base;
DROP TABLE IF EXISTS tbl_fcff_normalised;
DROP TABLE IF EXISTS tbl_fcff_sector_calculated;
DROP TABLE IF EXISTS tbl_fcff_driver_forecast;
DROP TABLE IF EXISTS tbl_fcff_driver_pv;
DROP TABLE IF EXISTS tbl_nopat_forecast;
DROP TABLE IF EXISTS tbl_revenue_growth;
DROP TABLE IF EXISTS tbl_growth_final;
DROP TABLE IF EXISTS tbl_revenue_forecast;
DROP TABLE IF EXISTS tbl_driver_assumptions;

-- Terminal & valuation
DROP TABLE IF EXISTS tbl_terminal_growth;
DROP TABLE IF EXISTS tbl_terminal_value;
DROP TABLE IF EXISTS tbl_enterprise_value;
DROP TABLE IF EXISTS tbl_equity_value;
DROP TABLE IF EXISTS tbl_intrinsic_price;
DROP TABLE IF EXISTS tbl_intrinsic_price_driver;
DROP TABLE IF EXISTS tbl_final_valuation;

-- Any intermediate views
DROP VIEW IF EXISTS vw_latest_march;
""")

print("✅ All FCFF, growth, and valuation objects removed")


# In[489]:


#STEP 0 — LATEST MARCH SNAPSHOTS (MANDATORY)


# In[581]:


con.execute("""
CREATE OR REPLACE VIEW vw_latest_march AS
SELECT *
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY stock_id
               ORDER BY period_end DESC
           ) AS rn
    FROM income_statement_calculated
    WHERE EXTRACT(month FROM period_end) = 3
)
WHERE rn = 1;
""")

con.execute("""
CREATE OR REPLACE VIEW vw_latest_march_balance AS
SELECT *
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY stock_id
               ORDER BY period_end DESC
           ) AS rn
    FROM balance_sheet_calculated
    WHERE EXTRACT(month FROM period_end) = 3
)
WHERE rn = 1;
""")


# In[583]:


con.execute("""
SELECT sm.symbol, revenue, ebit, depreciation
FROM vw_latest_march v
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[584]:


#STEP 1 — REVENUE GROWTH (MAX OF 3Y, 5Y)


# In[585]:


con.execute("""
DROP TABLE IF EXISTS tbl_revenue_growth;

CREATE TABLE tbl_revenue_growth AS
WITH base AS (
    SELECT
        stock_id,
        period_end,
        revenue,
        LAG(revenue, 3) OVER (PARTITION BY stock_id ORDER BY period_end) AS rev_3y,
        LAG(revenue, 5) OVER (PARTITION BY stock_id ORDER BY period_end) AS rev_5y
    FROM income_statement_calculated
    WHERE EXTRACT(month FROM period_end) = 3
),
calc AS (
    SELECT
        stock_id,
        POWER(revenue / rev_3y, 1.0/3) - 1 AS g_3y,
        POWER(revenue / rev_5y, 1.0/5) - 1 AS g_5y,
        ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY period_end DESC) AS rn
    FROM base
)
SELECT
    stock_id,
    GREATEST(g_3y, g_5y) AS revenue_growth
FROM calc
WHERE rn = 1;
""")


# In[587]:


con.execute("""
SELECT sm.symbol, ROUND(revenue_growth*100,2) AS rev_g_pct
FROM tbl_revenue_growth g
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[588]:


#STEP 2 — EBIT MARGIN (AVG 3Y)


# In[589]:


con.execute("""
DROP TABLE IF EXISTS tbl_ebit_margin;

CREATE TABLE tbl_ebit_margin AS
WITH hist AS (
    SELECT
        stock_id,
        ebit / NULLIF(revenue, 0) AS margin,
        ROW_NUMBER() OVER (
            PARTITION BY stock_id
            ORDER BY period_end DESC
        ) AS rn
    FROM income_statement_calculated
    WHERE EXTRACT(month FROM period_end) = 3
)
SELECT
    stock_id,
    AVG(margin) FILTER (WHERE rn <= 3) AS ebit_margin
FROM hist
GROUP BY stock_id;
""")

print("✅ STEP 2: EBIT margin (3Y average) created")


# In[591]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(ebit_margin * 100, 2) AS ebit_margin_pct
FROM tbl_ebit_margin m
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE', 'ASIANPAINT', 'BEL');
""").df()


# In[592]:


#STEP 3 — NET CAPEX INTENSITY (AVG)


# In[594]:


con.execute("""
DROP TABLE IF EXISTS tbl_net_capex_intensity;

CREATE TABLE tbl_net_capex_intensity AS
WITH hist AS (
    SELECT
        isc.stock_id,
        ((-1 * cfc.capex) - isc.depreciation)
        / NULLIF(
            isc.revenue - LAG(isc.revenue) OVER (
                PARTITION BY isc.stock_id ORDER BY isc.period_end
            ),
            0
        ) AS capex_ratio,
        ROW_NUMBER() OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end DESC) AS rn
    FROM income_statement_calculated isc
    JOIN cashflow_calculated cfc
      ON isc.stock_id = cfc.stock_id
     AND isc.period_end = cfc.period_end
    WHERE EXTRACT(month FROM isc.period_end) = 3
)
SELECT
    stock_id,
    AVG(capex_ratio) FILTER (WHERE rn <= 5) AS net_capex_intensity
FROM hist
GROUP BY stock_id;
""")


# In[596]:


con.execute("""
SELECT sm.symbol, ROUND(net_capex_intensity,3)
FROM tbl_net_capex_intensity
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[597]:


#STEP 4 — WORKING CAPITAL INTENSITY (AVG)


# In[598]:


con.execute("""
DROP TABLE IF EXISTS tbl_wc_intensity;

CREATE TABLE tbl_wc_intensity AS
WITH hist AS (
    SELECT
        isc.stock_id,
        cfc.working_capital_changes
        / NULLIF(
            isc.revenue - LAG(isc.revenue) OVER (
                PARTITION BY isc.stock_id ORDER BY isc.period_end
            ),
            0
        ) AS wc_ratio,
        ROW_NUMBER() OVER (PARTITION BY isc.stock_id ORDER BY isc.period_end DESC) AS rn
    FROM income_statement_calculated isc
    JOIN cashflow_calculated cfc
      ON isc.stock_id = cfc.stock_id
     AND isc.period_end = cfc.period_end
    WHERE EXTRACT(month FROM isc.period_end) = 3
)
SELECT
    stock_id,
    AVG(wc_ratio) FILTER (WHERE rn <= 5) AS wc_intensity
FROM hist
GROUP BY stock_id;
""")


# In[600]:


con.execute("""
SELECT sm.symbol, ROUND(wc_intensity,3)
FROM tbl_wc_intensity
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[601]:


#STEP 5 — REVENUE FORECAST (7 YEARS)


# In[602]:


con.execute("""
DROP TABLE IF EXISTS tbl_revenue_forecast;

CREATE TABLE tbl_revenue_forecast AS
SELECT
    v.stock_id,
    yr,
    v.revenue * POWER(1 + g.revenue_growth, yr) AS revenue_t
FROM vw_latest_march v
JOIN tbl_revenue_growth g USING (stock_id)
CROSS JOIN (SELECT UNNEST([1,2,3,4,5,6,7]) AS yr);
""")


# In[603]:


con.execute("""
SELECT sm.symbol, yr, ROUND(revenue_t,0)
FROM tbl_revenue_forecast
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINTS','BEL');
""").df()


# In[604]:


#STEP 6 — FCFF (FINAL, CORRECT)


# In[605]:


con.execute("""
DROP TABLE IF EXISTS tbl_fcff_forecast;

CREATE TABLE tbl_fcff_forecast AS
WITH base AS (
    SELECT
        r.stock_id,
        r.yr,
        r.revenue_t,
        v.revenue AS revenue_0,
        m.ebit_margin,
        v.tax_expense_percent / 100.0 AS tax_rate,
        c.net_capex_intensity,
        w.wc_intensity,
        LAG(r.revenue_t) OVER (PARTITION BY r.stock_id ORDER BY r.yr) AS prev_rev
    FROM tbl_revenue_forecast r
    JOIN vw_latest_march v USING (stock_id)
    JOIN tbl_ebit_margin m USING (stock_id)
    JOIN tbl_net_capex_intensity c USING (stock_id)
    JOIN tbl_wc_intensity w USING (stock_id)
)
SELECT
    stock_id,
    yr,

    -- NOPAT
    revenue_t * ebit_margin * (1 - tax_rate) AS nopat,

    -- Incremental CAPEX (declining)
    (
        CASE WHEN yr = 1 THEN revenue_t - revenue_0
             ELSE revenue_t - prev_rev
        END
    ) * net_capex_intensity
      * (0.75 - (yr - 1)*(0.75-0.30)/6) AS incr_capex,

    -- Incremental WC
    (
        CASE WHEN yr = 1 THEN revenue_t - revenue_0
             ELSE revenue_t - prev_rev
        END
    ) * wc_intensity AS delta_wc,

    -- FCFF
    (revenue_t * ebit_margin * (1 - tax_rate))
    - (
        (CASE WHEN yr = 1 THEN revenue_t - revenue_0
              ELSE revenue_t - prev_rev
         END) * net_capex_intensity
         * (0.75 - (yr - 1)*(0.75-0.30)/6)
      )
    + (
        (CASE WHEN yr = 1 THEN revenue_t - revenue_0
              ELSE revenue_t - prev_rev
         END) * wc_intensity
      ) AS fcff

FROM base;
""")


# In[608]:


con.execute("""
SELECT sm.symbol, yr, ROUND(fcff,0)
FROM tbl_fcff_forecast
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[612]:


#STEP 7A — Create tbl_terminal_growth


# In[642]:


con.execute("""
DROP TABLE IF EXISTS tbl_terminal_growth;

CREATE TABLE tbl_terminal_growth AS
SELECT
    stock_id,
    CASE
        WHEN sector IN ('Consumer Durables', 'Consumer Staples', 'Paints')
            THEN 0.04
        WHEN sector IN ('Capital Goods', 'Defence')
            THEN 0.04
        WHEN sector IN ('Energy', 'Oil & Gas', 'Conglomerates')
            THEN 0.05
        WHEN sector IN ('Information Technology', 'IT Services')
            THEN 0.05
        WHEN sector IN ('Utilities')
            THEN 0.025
        ELSE 0.03
    END AS terminal_growth
FROM stocks_master;
""")


# In[643]:


con.execute("""
SELECT
    sm.symbol,
    sm.sector,
    tg.terminal_growth * 100 AS terminal_g_pct
FROM tbl_terminal_growth tg
JOIN stocks_master sm
  ON tg.stock_id = sm.stock_id
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[619]:


#STEP 7B — TERMINAL VALUE (GUARDED)


# In[644]:


con.execute("""
DROP TABLE IF EXISTS tbl_terminal_value;

CREATE TABLE tbl_terminal_value AS
SELECT
    f.stock_id,

    -- growth used after guard
    CASE
        WHEN tg.terminal_growth >= w.wacc
        THEN w.wacc - 0.02
        ELSE tg.terminal_growth
    END AS terminal_growth_used,

    -- terminal value
    f.fcff
    * (1 + CASE
                WHEN tg.terminal_growth >= w.wacc
                THEN w.wacc - 0.02
                ELSE tg.terminal_growth
           END)
    / NULLIF(
        w.wacc -
        CASE
            WHEN tg.terminal_growth >= w.wacc
            THEN w.wacc - 0.02
            ELSE tg.terminal_growth
        END,
        0
    ) AS terminal_value

FROM tbl_fcff_forecast f
JOIN vw_wacc_latest w
  ON f.stock_id = w.stock_id
JOIN tbl_terminal_growth tg
  ON f.stock_id = tg.stock_id
WHERE f.yr = 7;
""")

print("✅ STEP 7B: Terminal value created")


# In[645]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(terminal_growth_used*100,2) AS terminal_g_used_pct,
    ROUND(terminal_value,0) AS terminal_value_cr
FROM tbl_terminal_value tv
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[623]:


#STEP 8A — PV of FCFF (Years 1–7)


# In[646]:


con.execute("""
DROP TABLE IF EXISTS tbl_fcff_pv;

CREATE TABLE tbl_fcff_pv AS
SELECT
    f.stock_id,
    SUM(
        f.fcff / POWER(1 + w.wacc, f.yr)
    ) AS pv_fcff
FROM tbl_fcff_forecast f
JOIN vw_wacc_latest w
  ON f.stock_id = w.stock_id
GROUP BY f.stock_id;
""")

print("✅ STEP 8A: PV of FCFF created")


# In[647]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(pv_fcff,0) AS pv_fcff_cr
FROM tbl_fcff_pv
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[627]:


#STEP 8B — PV of Terminal Value


# In[648]:


con.execute("""
DROP TABLE IF EXISTS tbl_terminal_value_pv;

CREATE TABLE tbl_terminal_value_pv AS
SELECT
    tv.stock_id,
    tv.terminal_value / POWER(1 + w.wacc, 7) AS pv_terminal_value
FROM tbl_terminal_value tv
JOIN vw_wacc_latest w
  ON tv.stock_id = w.stock_id;
""")

print("✅ STEP 8B: PV of terminal value created")


# In[629]:


#STEP 8C — Enterprise Value


# In[649]:


con.execute("""
DROP TABLE IF EXISTS tbl_enterprise_value;

CREATE TABLE tbl_enterprise_value AS
SELECT
    f.stock_id,
    f.pv_fcff + t.pv_terminal_value AS enterprise_value
FROM tbl_fcff_pv f
JOIN tbl_terminal_value_pv t
  ON f.stock_id = t.stock_id;
""")

print("✅ STEP 8C: Enterprise value created")


# In[650]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(enterprise_value,0) AS ev_cr
FROM tbl_enterprise_value
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[633]:


#STEP 8D — Equity Value


# In[651]:


con.execute("""
DROP TABLE IF EXISTS tbl_equity_value;

CREATE TABLE tbl_equity_value AS
SELECT
    e.stock_id,
    e.enterprise_value - b.net_debt AS equity_value
FROM tbl_enterprise_value e
JOIN vw_latest_march_balance b
  ON e.stock_id = b.stock_id;
""")

print("✅ STEP 8D: Equity value created")


# In[652]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(equity_value,0) AS equity_value_cr
FROM tbl_equity_value
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');
""").df()


# In[653]:


con.execute("""
DROP TABLE IF EXISTS tbl_intrinsic_price;

CREATE TABLE tbl_intrinsic_price AS
SELECT
    e.stock_id,
    (e.equity_value * 1e7) / v.shares_outstanding AS intrinsic_price
FROM tbl_equity_value e
JOIN vw_latest_march v
  ON e.stock_id = v.stock_id;
""")

print("✅ STEP 8E: Intrinsic price created")


# In[654]:


con.execute("""
SELECT
    sm.symbol,
    ROUND(ip.intrinsic_price, 2) AS intrinsic_price_rs,
    ROUND(v.shares_outstanding, 2) AS shares_outstanding
FROM tbl_intrinsic_price ip
JOIN stocks_master sm
  ON ip.stock_id = sm.stock_id
JOIN vw_latest_march v
  ON ip.stock_id = v.stock_id
WHERE sm.symbol IN ('RELIANCE','ASIANPAINT','BEL');

""").df()

