"""
Quality stock candidates pre-selected based on known moat / compounder characteristics.
Screener will score these on quantitative criteria and rank them.
"""

US_CANDIDATES = [
    # Payments / Financial infrastructure
    {"ticker": "V",     "name": "Visa",               "sector": "Financials"},
    {"ticker": "MA",    "name": "Mastercard",          "sector": "Financials"},
    {"ticker": "SPGI",  "name": "S&P Global",          "sector": "Financials"},
    {"ticker": "MCO",   "name": "Moody's",             "sector": "Financials"},
    # Software / Platform
    {"ticker": "MSFT",  "name": "Microsoft",           "sector": "Technology"},
    {"ticker": "ADBE",  "name": "Adobe",               "sector": "Technology"},
    {"ticker": "FICO",  "name": "FICO",                "sector": "Technology"},
    {"ticker": "NOW",   "name": "ServiceNow",          "sector": "Technology"},
    # Healthcare / MedTech
    {"ticker": "UNH",   "name": "UnitedHealth",        "sector": "Healthcare"},
    {"ticker": "ISRG",  "name": "Intuitive Surgical",  "sector": "Healthcare"},
    {"ticker": "TMO",   "name": "Thermo Fisher",       "sector": "Healthcare"},
    {"ticker": "LLY",   "name": "Eli Lilly",           "sector": "Healthcare"},
    # Consumer / Retail
    {"ticker": "COST",  "name": "Costco",              "sector": "Consumer"},
    {"ticker": "MNST",  "name": "Monster Beverage",    "sector": "Consumer"},
    # Industrials
    {"ticker": "ODFL",  "name": "Old Dominion Freight","sector": "Industrials"},
    {"ticker": "AXON",  "name": "Axon Enterprise",     "sector": "Industrials"},
    # Semiconductor
    {"ticker": "NVDA",  "name": "Nvidia",              "sector": "Technology"},
    {"ticker": "AVGO",  "name": "Broadcom",            "sector": "Technology"},
    # Insurance / Specialty
    {"ticker": "BRO",   "name": "Brown & Brown",       "sector": "Financials"},
    {"ticker": "RLI",   "name": "RLI Corp",            "sector": "Financials"},
]

JP_CANDIDATES = [
    # Precision / Industrial
    {"ticker": "6861.T", "name": "キーエンス",         "sector": "Technology"},
    {"ticker": "6273.T", "name": "SMC",               "sector": "Industrials"},
    {"ticker": "7741.T", "name": "HOYA",              "sector": "Healthcare"},
    {"ticker": "6098.T", "name": "リクルートHD",       "sector": "Services"},
    # Healthcare / Pharma
    {"ticker": "4519.T", "name": "中外製薬",           "sector": "Healthcare"},
    {"ticker": "4543.T", "name": "テルモ",             "sector": "Healthcare"},
    {"ticker": "2413.T", "name": "エムスリー",         "sector": "Healthcare"},
    # Consumer / Retail
    {"ticker": "9983.T", "name": "ファーストリテイリング","sector": "Consumer"},
    {"ticker": "7974.T", "name": "任天堂",             "sector": "Consumer"},
    {"ticker": "4661.T", "name": "オリエンタルランド", "sector": "Consumer"},
    # Industrials / Auto
    {"ticker": "7203.T", "name": "トヨタ自動車",       "sector": "Industrials"},
    {"ticker": "6501.T", "name": "日立製作所",         "sector": "Industrials"},
    # Financial
    {"ticker": "8316.T", "name": "三井住友FG",         "sector": "Financials"},
    # Software / IT
    {"ticker": "3697.T", "name": "SHIFT",             "sector": "Technology"},
    {"ticker": "4307.T", "name": "野村総合研究所",     "sector": "Technology"},
]
