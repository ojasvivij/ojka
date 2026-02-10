#!/usr/bin/env python
# coding: utf-8

# In[1]:


#STEP 0 — IMPORTS & GLOBALS


# In[2]:


import duckdb
import pandas as pd
import re
from pathlib import Path
from collections import defaultdict


# In[3]:


DB_PATH = "data/market_data.duckdb"
DATA_DIR = Path("data/raw/financials")
FILES = list(DATA_DIR.glob("*_financials.xlsx"))


# In[4]:


#STEP 1 — RESET DATABASE (DROP TABLES)


# In[5]:


con = duckdb.connect(DB_PATH)

for t in [
    "financial_income_statement",
    "financial_balance_sheet",
    "financial_cashflow",
    "financial_quarterly_results",
    "shareholding_pattern",
    "stocks_master"
]:
    con.execute(f"DROP TABLE IF EXISTS {t}")

con.close()
print("✅ Step 1: Database reset")


# In[6]:


#STEP 2 — CREATE ALL SCHEMAS (EXACT)


# In[7]:


con = duckdb.connect(DB_PATH)

con.execute("""
CREATE TABLE stocks_master (
    stock_id INTEGER PRIMARY KEY,
    symbol TEXT,
    company_name TEXT,
    sector TEXT,
    industry TEXT
)
""")


# ---------- INCOME STATEMENT ----------
con.execute("""
CREATE TABLE financial_income_statement (
    stock_id INTEGER,
    period_end DATE,
    revenue DOUBLE,
    ebitda DOUBLE,
    operating_profit DOUBLE,
    interest_expense DOUBLE,
    depreciation DOUBLE,
    ebt DOUBLE,
    tax_expense_percent DOUBLE,
    net_income DOUBLE,
    net_income_adj DOUBLE,
    eps DOUBLE,
    dividend_Payout_ratio DOUBLE,
    PRIMARY KEY (stock_id, period_end)
)
""")

# ---------- BALANCE SHEET ----------
con.execute("""
CREATE TABLE financial_balance_sheet (
    stock_id INTEGER,
    period_end DATE,

    cash_and_equivalents DOUBLE,
    inventories DOUBLE,
    trade_receivables DOUBLE,
    loans_n_advances DOUBLE,
    other_asset_items DOUBLE,

    fixed_assets DOUBLE,
    gross_block DOUBLE,
    accumulated_depreciation DOUBLE,
    cwip DOUBLE,
    investments DOUBLE,
    total_assets DOUBLE,

    deposits DOUBLE,
    borrowings DOUBLE,
    long_term_borrowings DOUBLE,
    short_term_borrowings DOUBLE,
    other_borrowings DOUBLE,
    lease_liab DOUBLE,

    advance_from_customers DOUBLE,
    non_controlling_int DOUBLE,
    trade_payables DOUBLE,
    other_liability_items DOUBLE,

    equity_share_capital DOUBLE,
    equity_reserves DOUBLE,
    total_liabilities_Equity DOUBLE,

    PRIMARY KEY (stock_id, period_end)
)
""")

# ---------- CASH FLOW ----------
con.execute("""
CREATE TABLE financial_cashflow (
    stock_id INTEGER,
    period_end DATE,
    profit_from_operations DOUBLE,
    receivables DOUBLE,
    inventory DOUBLE,
    payables DOUBLE,
    direct_taxes DOUBLE,
    loans_advances DOUBLE,
    operating_investments DOUBLE,
    operating_deposits DOUBLE,
    other_wc_items DOUBLE,
    working_capital_changes DOUBLE,
    cash_from_operating_activity DOUBLE,

    
    fixed_assets_purchased DOUBLE,
    fixed_assets_sold DOUBLE,
    investments_purchased DOUBLE,
    investments_sold DOUBLE,
    interest_received DOUBLE,
    dividends_received DOUBLE,
    invest_in_subsidiaries DOUBLE,
    acquisition_of_companies DOUBLE,
    other_investing_items DOUBLE,
    cash_from_investing_activity DOUBLE,

    
    proceeds_from_shares DOUBLE,
    proceeds_from_borrowings DOUBLE,
    repayment_of_borrowings DOUBLE,
    proceeds_from_debentures DOUBLE,
    redemption_of_debentures DOUBLE,
    interest_paid_fin DOUBLE,
    dividends_paid DOUBLE,
    financial_liabilities DOUBLE,
    share_application_money DOUBLE,
    other_financing_items DOUBLE,
    cash_from_financing_activity DOUBLE,

    
    net_cash_flow DOUBLE,

    
    PRIMARY KEY (stock_id, period_end)
)
""")

# ---------- QUARTERLY ----------
con.execute("""
CREATE TABLE financial_quarterly_results (
    stock_id INTEGER,
    period_end DATE,
    revenue DOUBLE,
    ebitda DOUBLE,
    operating_profit DOUBLE,
    interest_expense DOUBLE,
    depreciation DOUBLE,
    ebt DOUBLE,
    tax_expense_percent DOUBLE,
    net_income DOUBLE,
    net_income_adj DOUBLE,
    eps DOUBLE,
    PRIMARY KEY (stock_id, period_end)
)
""")

# ---------- SHAREHOLDING ----------
con.execute("""
CREATE TABLE shareholding_pattern (
    stock_id INTEGER,
    period_end DATE,
    promoter_holding DOUBLE,
    fii_holding DOUBLE,
    dii_holding DOUBLE,
    government_holding DOUBLE,
    public_holding DOUBLE,

    PRIMARY KEY (stock_id, period_end)
)
""")

con.close()
print("✅ Step 2: Schemas created")


# In[8]:


#STEP 3 — POPULATE STOCK MASTER


# In[9]:


# STEP 3 — POPULATE STOCK MASTER (FROM TICKERS)

import pandas as pd
import duckdb

# Read tickers
tickers = pd.read_excel("data/raw/Tickers.xlsx")
tickers.columns = tickers.columns.str.lower().str.strip()

# Rename columns (type IS THE SOURCE OF TRUTH)
tickers = tickers.rename(columns={
    "ticker": "symbol",
    "name": "company_name",
    "type": "industry"
})

# Deduplicate
tickers = tickers.drop_duplicates("symbol").reset_index(drop=True)

# Assign stock_id
tickers["stock_id"] = range(1, len(tickers) + 1)

# Keep exact schema expected by stocks_master
tickers = tickers[["stock_id", "symbol", "company_name", "sector", "industry"]]

# Load into DuckDB
con = duckdb.connect(DB_PATH)

# Clear and reload (intentional reset)
con.execute("DELETE FROM stocks_master")

con.register("tickers_df", tickers)
con.execute("""
INSERT INTO stocks_master
SELECT * FROM tickers_df
""")

con.close()

print("✅ stocks_master populated from Tickers.xlsx (industry preserved exactly)")


# In[10]:


import duckdb

con = duckdb.connect(DB_PATH)

stock_map = dict(
    con.execute(
        "SELECT UPPER(symbol), stock_id FROM stocks_master"
    ).fetchall()
)

con.close()

print("✅ stock_map built:", len(stock_map))


# In[11]:


#STEP 4 — HELPERS (NORMALIZATION, PARSING)


# In[12]:


import pandas as pd
import re

def normalize_key(x):
    if pd.isna(x):
        return ""
    x = str(x).lower()
    x = re.sub(r"\(.*?\)", "", x)
    x = re.sub(r"[^a-z %]", "", x)
    return x.strip()

def clean_number(x):
    if pd.isna(x):
        return None
    x = str(x).replace(",", "").strip()
    if "%" in x:
        return float(x.replace("%", ""))
    try:
        return float(x)
    except:
        return None

def parse_period(col):
    if str(col).upper() == "TTM":
        return None
    try:
        return pd.to_datetime(col).date()
    except:
        return None


# In[13]:


#STEP 6 — CANONICAL MAPPINGS (FROM STEP 5)


# In[14]:


PL_MAP = {
    "revenue": ["sales", "revenue"],
    "interest_expense": ["interest"],
    "ebitda": ["operating profit"],
    "operating_profit": ["financing profit"],
    "depreciation": ["depreciation"],
    "ebt" : ["profit before tax"],
    "tax_expense_percent": ["tax %"],
    "net_income": ["net profit"],
    "net_income_adj": ["profit for eps"],
    "eps": ["eps in rs"],
    "dividend_Payout_ratio": ["dividend payout %"]
}


BS_MAP = {


    "cash_and_equivalents" : ["cash equivalents","Cash Equivalents"],
    "inventories" : ["inventories"],
    "trade_receivables" : ["trade receivables"],
    "loans_n_advances" : ["loans n advances"],
    "other_asset_items" : ["other asset items"],

    "fixed_assets" : ["fixed assets"],
    "gross_block"  : ["gross block"],
    "accumulated_depreciation" : ["accumulated depreciation"],
    "cwip" :  ["cwip"],
    "investments" : ["investments"],

    "total_assets" : ["total assets"],

    
    "deposits" :["deposits"],
    "borrowings" : ["borrowings","borrowing","Borrowing"],
    "long_term_borrowings": ["long term borrowings"],
    "short_term_borrowings": ["short term borrowings"],
    "other_borrowings": ["other borrowings"],
    "lease_liab": ["lease liabilities"],

    "advance_from_customers" : ["advance from customers"],
    "non_controlling_int" : ["non controlling int"],
    "trade_payables" : ["trade payables"],
    "other_liability_items" : ["other liability items"],
     
    "equity_share_capital" : ["equity share capital","equity capital","Equity Capital"],
    "equity_reserves" : ["reserves","Reserves"],

    "total_liabilities_Equity" : ["total liabilities"]

}


CF_MAP = {

    "profit_from_operations": ["profit from operations"],
    "receivables" : ["receivables"],
    "inventory" : ["inventory"],
    "payables" : ["payables"],
    "direct_taxes" : ["direct taxes"],
    "loans_advances" : ["loans advances"],
    "operating_investments" : ["operating investments","Operating investments"],
    "operating_deposits" : ["operating deposits","Operating Deposits"],
    "other_wc_items" : ["other wc items","Other WC items"],
    "working_capital_changes" : ["working capital changes","Working capital changes"],
    "cash_from_operating_activity": ["cash from operating activity","Cash from Operating Activity"],


    "fixed_assets_purchased": ["fixed assets purchased","Fixed assets purchased"],
    "fixed_assets_sold": ["fixed assets sold","Fixed assets sold"],
    "investments_purchased" : ["investments purchased","Investments purchased"],
    "investments_sold" : ["investments sold","Investments sold"],
    "interest_received": ["interest received","Interest received"],
    "dividends_received": ["dividends received","Dividends received"],
    "invest_in_subsidiaries" : ["invest in subsidiaries","Invest in subsidiaries"],
    "acquisition_of_companies" : ["acquisition of companies","Acquisition of companies"],
    "other_investing_items" : ["other investing items","Other investing items"],
    "cash_from_investing_activity" : ["cash from investing activity","Cash from Investing Activity"],

    "proceeds_from_shares" : ["proceeds from shares","Proceeds from shares"],
    "proceeds_from_borrowings": ["proceeds from borrowings","Proceeds from borrowings"],
    "repayment_of_borrowings": ["repayment of borrowings","Repayment of borrowings"],
    "proceeds_from_debentures" : ["proceeds from debentures","Proceeds from debentures"],
    "redemption_of_debentures" : ["redemption of debentures","Redemption of debentures"],
    "interest_paid_fin": ["interest paid","Interest paid fin","interest paid fin"],
    "dividends_paid": ["dividends paid","Dividends paid"],
    "financial_liabilities" : ["financial liabilities","Financial liabilities"],
    "share_application_money" : ["share application money","Share application money"],
    "other_financing_items" : ["other financing items","Other financing items"],
    
    "cash_from_financing_activity" : ["cash from financing activity","Cash from Financing Activity"],

    "net_cash_flow": ["net cash flow","Net Cash Flow"]
}


QR_MAP = {
    "revenue": ["sales", "revenue"],
    "interest_expense": ["interest"],
    "ebitda": ["operating profit"],
    "operating_profit": ["financing profit"],
    "depreciation": ["depreciation"],
    "ebt" : ["profit before tax"],
    "tax_expense_percent": ["tax %"],
    "net_income": ["net profit"],
    "net_income_adj": ["profit for eps"],
    "eps": ["eps in rs"]

}


SHAREHOLDING_MAP = {
    "promoter_holding": ["promoters"],
    "fii_holding": ["fiis"],
    "dii_holding": ["diis"],
    "government_holding": ["government"],
    "public_holding": ["public"]
}


# In[15]:


#STEP 7 — EXTRACTORS


# In[16]:


def extract_from_map(df, col, mapping):
    out = {}
    for _, r in df.iterrows():
        key = normalize_key(r.get("line_item", ""))
        val = clean_number(r[col])
        for canon, aliases in mapping.items():
            if canon not in out:
                for a in aliases:
                    if a in key:
                        out[canon] = val
    return out

def extract_shareholding(df, col, SHAREHOLDING_MAP):
    out = {k: None for k in SHAREHOLDING_MAP}
    for _, r in df.iterrows():
        key = normalize_key(r["category"])
        val = clean_number(r[col])
        for canon, aliases in SHAREHOLDING_MAP.items():
            for a in aliases:
                if a in key and out[canon] is None:
                    out[canon] = val
    return out


# In[17]:


#8.2 PROFIT & LOSS — RAW INGEST


# In[18]:


con = duckdb.connect(DB_PATH)
for f in FILES:
    symbol = f.stem.replace("_financials", "").upper()
    stock_id = stock_map[symbol]

    xl = pd.ExcelFile(f)

    if "Profit & Loss" not in xl.sheet_names:
        continue

    df = xl.parse("Profit & Loss")
    df.columns = df.columns.str.lower().str.strip()

    for col in df.columns:
        period = parse_period(col)
        if period is None:
            continue

        v = extract_from_map(df, col, PL_MAP)

        con.execute("""
        INSERT OR REPLACE INTO financial_income_statement
        (
            stock_id, period_end,
            revenue, interest_expense,ebitda, operating_profit,
            depreciation, ebt ,tax_expense_percent,
            net_income, net_income_adj,
            eps, dividend_Payout_ratio
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            stock_id,
            period,
            v.get("revenue"),
            v.get("interest_expense"),
            v.get("ebitda"),
            v.get("operating_profit"),
            v.get("depreciation"),
            v.get("ebt"),
            v.get("tax_expense_percent"),
            v.get("net_income"),
            v.get("net_income_adj"),
            v.get("eps"),
            v.get("dividend_Payout_ratio")
        ])


    if "Balance Sheet" not in xl.sheet_names:
        continue

    df = xl.parse("Balance Sheet")
    df.columns = df.columns.str.lower().str.strip()

    for col in df.columns:
        period = parse_period(col)
        if period is None:
            continue

        v = extract_from_map(df, col, BS_MAP)

        con.execute("""
        INSERT OR REPLACE INTO financial_balance_sheet
        (
            stock_id, period_end,
            cash_and_equivalents, inventories, trade_receivables,
            loans_n_advances, other_asset_items,
            fixed_assets, gross_block, accumulated_depreciation,
            cwip, investments, total_assets,
            deposits, borrowings,
            long_term_borrowings, short_term_borrowings, other_borrowings,
            lease_liab, advance_from_customers, non_controlling_int,
            trade_payables, other_liability_items,
            equity_share_capital, equity_reserves,
            total_liabilities_Equity
            
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
        """, [
            stock_id, period,
            
            v.get("cash_and_equivalents"),
            v.get("inventories"),
            v.get("trade_receivables"),
            v.get("loans_n_advances"),
            v.get("other_asset_items"),
            
            v.get("fixed_assets"),
            v.get("gross_block"),
            v.get("accumulated_depreciation"),
            v.get("cwip"),
            v.get("investments"),
            v.get("total_assets"),

            v.get("deposits"),
            v.get("borrowings"),
            v.get("long_term_borrowings"),
            v.get("short_term_borrowings"),
            v.get("other_borrowings"),
            v.get("lease_liab"),

            v.get("advance_from_customers"),
            v.get("non_controlling_int"),
            v.get("trade_payables"),
            v.get("other_liability_items"),

            
            v.get("equity_share_capital"),
            v.get("equity_reserves"),
        
            v.get("total_liabilities_Equity")
            
        ])




    if "Cash Flows" not in xl.sheet_names:
        continue

    df = xl.parse("Cash Flows")
    df.columns = df.columns.str.lower().str.strip()

    for col in df.columns:
        period = parse_period(col)
        if period is None:
            continue

        v = extract_from_map(df, col, CF_MAP)

        con.execute("""
        INSERT OR REPLACE INTO financial_cashflow
     
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            stock_id,
            period,
            v.get("profit_from_operations"),
            v.get("receivables"),
            v.get("inventory"),
            v.get("payables"),
            v.get("direct_taxes"),
            v.get("loans_advances"),
            v.get("operating_investments"),
            v.get("operating_deposits"),
            v.get("other_WC_items"),
            v.get("working_capital_changes"),
            v.get("cash_from_operating_activity"),
            
            v.get("fixed_assets_purchased"),
            v.get("fixed_assets_sold"),
            v.get("investments_purchased"),
            v.get("investments_sold"),
            v.get("interest_received"),
            v.get("dividends_received"),
            v.get("invest_in_subsidiaries"),
            v.get("acquisition_of_companies"),
            v.get("other_investing_items"),
            v.get("cash_from_investing_activity"),
            
            v.get("proceeds_from_shares"),
            v.get("proceeds_from_borrowings"),
            v.get("repayment_of_borrowings"),
            v.get("proceeds_from_debentures"),
            v.get("redemption_of_debentures"),
            v.get("interest_paid_fin"),
            v.get("dividends_paid"),
            v.get("financial_liabilities"),
            v.get("share_application_money"),
            v.get("other_financing_items"),
            v.get("cash_from_financing_activity"),
            
            v.get("net_cash_flow")
        ])

    if "Quarterly Results" not in xl.sheet_names:
        continue

    df = xl.parse("Quarterly Results")
    df.columns = df.columns.str.lower().str.strip()

    for col in df.columns:
        period = parse_period(col)
        if period is None:
            continue

        v = extract_from_map(df, col, QR_MAP)

        con.execute("""
        INSERT OR REPLACE INTO financial_quarterly_results
        (
            stock_id, period_end,
            revenue,
            interest_expense,ebitda , operating_profit ,depreciation,ebt, tax_expense_percent,
            net_income, net_income_adj, eps
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            stock_id,
            period,
            v.get("revenue"),
            v.get("interest_expense"),
            v.get("ebitda"),
            v.get("operating_profit"),
            v.get("depreciation"),
            v.get("ebt"),
            v.get("tax_expense_percent"),
            v.get("net_income"),
            v.get("net_income_adj"),
            v.get("eps"),
        ])


    if "Shareholding Pattern" not in xl.sheet_names:
        continue

    df = xl.parse("Shareholding Pattern")
    df.columns = df.columns.str.lower().str.strip()

    for col in df.columns:
        period = parse_period(col)
        if period is None:
            continue

        v = extract_shareholding(df, col, SHAREHOLDING_MAP)

        con.execute("""
        INSERT OR REPLACE INTO shareholding_pattern
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            stock_id,
            period,
            v.get("promoter_holding"),
            v.get("fii_holding"),
            v.get("dii_holding"),
            v.get("government_holding"),
            v.get("public_holding"),
        ])

con.close()
print("✅ STEP 8 COMPLETE — RAW DATA INGESTED")


# In[19]:


None           # shares_outstanding calculated later


# In[20]:


import duckdb

con = duckdb.connect("data/market_data.duckdb")

con.execute("SHOW TABLES").df()


# In[21]:


con.execute("""
SELECT *
FROM stocks_master
LIMIT 20
""").df()


# In[22]:


con.execute("""
SELECT *
FROM financial_balance_sheet
LIMIT 20
""").df()


# In[23]:


con.execute("""
SELECT *
FROM financial_cashflow
LIMIT 20
""").df()


# In[24]:


con.execute("""
SELECT *
FROM financial_quarterly_results
LIMIT 20
""").df()


# In[25]:


con.execute("""
SELECT *
FROM shareholding_pattern
LIMIT 20
""").df()


# In[26]:


import duckdb

con = duckdb.connect("data/market_data.duckdb")

con.execute("SHOW TABLES").df()

con.execute("""
SELECT
*
FROM  financial_balance_sheet fi
JOIN stocks_master sm USING (stock_id)
WHERE sm.symbol = 'RELIANCE'
ORDER BY fi.period_end
LIMIT 20
""").df()


# In[27]:


con.close()

