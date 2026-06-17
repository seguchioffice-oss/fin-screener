"""
Scoring engine: evaluates each stock on 6 fundamental + 2 technical criteria.

Scoring breakdown (100 pts total):
  EPS multi-year growth    25 pts
  ROIC                     20 pts
  FCF / Net Income ratio   15 pts
  Dilution (share count)   15 pts
  Technical momentum       15 pts
  RSI / MA positioning     10 pts
"""

import numpy as np
import pandas as pd
import yfinance as yf
import time
import logging

logger = logging.getLogger(__name__)


def safe_get(info: dict, *keys, default=None):
    for k in keys:
        v = info.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return v
    return default


def fetch_ticker_data(ticker: str) -> dict:
    """Fetch all needed data for a ticker. Returns a flat dict."""
    result = {"ticker": ticker, "error": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # ── price / market data ────────────────────────────────────────
        result["price"] = safe_get(info, "currentPrice", "regularMarketPrice", "previousClose")
        result["market_cap"] = safe_get(info, "marketCap")
        result["currency"] = safe_get(info, "currency", default="USD")
        result["sector"] = safe_get(info, "sector", default="N/A")
        result["industry"] = safe_get(info, "industry", default="N/A")
        result["name"] = safe_get(info, "longName", "shortName", default=ticker)

        # ── EPS growth ────────────────────────────────────────────────
        # yfinance earnings history: 4 quarterly + forward
        try:
            ef = t.earnings_forecasts if hasattr(t, "earnings_forecasts") else None
        except Exception:
            ef = None

        # Use income statement for multi-year EPS
        try:
            fin = t.financials  # annual, index = metric, cols = dates
            if fin is not None and not fin.empty:
                net_income_row = None
                for label in ["Net Income", "Net Income From Continuing Operations"]:
                    if label in fin.index:
                        net_income_row = fin.loc[label]
                        break
                shares_row = None
                bs = t.balance_sheet
                if bs is not None and "Ordinary Shares Number" in bs.index:
                    shares_row = bs.loc["Ordinary Shares Number"]

                if net_income_row is not None and shares_row is not None:
                    eps_series = (net_income_row / shares_row).dropna().sort_index()
                    if len(eps_series) >= 3:
                        eps_vals = eps_series.values[-4:]  # up to 4 years
                        # CAGR over available years
                        n = len(eps_vals) - 1
                        if eps_vals[0] > 0 and eps_vals[-1] > 0:
                            result["eps_cagr"] = (eps_vals[-1] / eps_vals[0]) ** (1 / n) - 1
                        else:
                            result["eps_cagr"] = None
                        result["eps_series"] = list(eps_vals)
                    else:
                        result["eps_cagr"] = None
                else:
                    result["eps_cagr"] = None
            else:
                result["eps_cagr"] = None
        except Exception as e:
            result["eps_cagr"] = None
            logger.debug(f"{ticker} EPS error: {e}")

        # Fallback: use info fields
        if result["eps_cagr"] is None:
            eg = safe_get(info, "earningsGrowth")
            result["eps_cagr"] = eg  # trailing 12m growth

        # ── ROIC ─────────────────────────────────────────────────────
        try:
            fin = t.financials
            bs = t.balance_sheet
            cf = t.cashflow

            if fin is not None and bs is not None and not fin.empty and not bs.empty:
                # NOPAT = Operating Income * (1 - effective tax rate)
                op_inc = None
                for label in ["Operating Income", "EBIT"]:
                    if label in fin.index:
                        op_inc = fin.loc[label].iloc[0]
                        break

                tax_rate = 0.21  # default US corp tax
                pretax = fin.loc["Pretax Income"].iloc[0] if "Pretax Income" in fin.index else None
                tax_exp = fin.loc["Tax Provision"].iloc[0] if "Tax Provision" in fin.index else None
                if pretax and tax_exp and pretax != 0:
                    tax_rate = max(0, min(tax_exp / pretax, 0.40))

                nopat = op_inc * (1 - tax_rate) if op_inc else None

                # Invested Capital = Total Assets - Current Liabilities - Cash
                total_assets = bs.loc["Total Assets"].iloc[0] if "Total Assets" in bs.index else None
                curr_liab = bs.loc["Current Liabilities"].iloc[0] if "Current Liabilities" in bs.index else None
                cash = None
                for label in ["Cash And Cash Equivalents", "Cash"]:
                    if label in bs.index:
                        cash = bs.loc[label].iloc[0]
                        break
                cash = cash or 0

                if total_assets and curr_liab and nopat:
                    ic = total_assets - curr_liab - cash
                    result["roic"] = nopat / ic if ic > 0 else None
                else:
                    result["roic"] = None
            else:
                result["roic"] = None
        except Exception as e:
            result["roic"] = None
            logger.debug(f"{ticker} ROIC error: {e}")

        # Fallback to ROE/ROA from info
        if result["roic"] is None:
            roe = safe_get(info, "returnOnEquity")
            result["roic"] = roe

        # ── FCF / Net Income ──────────────────────────────────────────
        try:
            cf = t.cashflow
            fin = t.financials
            if cf is not None and fin is not None and not cf.empty and not fin.empty:
                ocf = None
                for label in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                    if label in cf.index:
                        ocf = cf.loc[label].iloc[0]
                        break
                capex = None
                for label in ["Capital Expenditure", "Capital Expenditures"]:
                    if label in cf.index:
                        capex = cf.loc[label].iloc[0]
                        break
                capex = capex or 0

                net_inc = None
                for label in ["Net Income", "Net Income From Continuing Operations"]:
                    if label in fin.index:
                        net_inc = fin.loc[label].iloc[0]
                        break

                if ocf is not None and net_inc and net_inc != 0:
                    fcf = ocf + capex  # capex is negative in cashflow statement
                    result["fcf_to_netinc"] = fcf / abs(net_inc)
                    result["fcf"] = fcf
                else:
                    result["fcf_to_netinc"] = None
                    result["fcf"] = safe_get(info, "freeCashflow")
            else:
                result["fcf_to_netinc"] = None
                result["fcf"] = safe_get(info, "freeCashflow")
        except Exception as e:
            result["fcf_to_netinc"] = None
            result["fcf"] = safe_get(info, "freeCashflow")
            logger.debug(f"{ticker} FCF error: {e}")

        # ── Dilution: share count change ──────────────────────────────
        try:
            bs = t.balance_sheet
            if bs is not None and "Ordinary Shares Number" in bs.index and bs.shape[1] >= 2:
                shares = bs.loc["Ordinary Shares Number"].dropna()
                if len(shares) >= 2:
                    newest = shares.iloc[0]
                    oldest = shares.iloc[-1]
                    n_years = len(shares) - 1
                    result["dilution_annual"] = (newest / oldest) ** (1 / n_years) - 1
                else:
                    result["dilution_annual"] = None
            else:
                result["dilution_annual"] = None
        except Exception as e:
            result["dilution_annual"] = None
            logger.debug(f"{ticker} dilution error: {e}")

        # ── Technical: price history ──────────────────────────────────
        try:
            hist = t.history(period="1y", interval="1d")
            if hist is not None and len(hist) > 50:
                closes = hist["Close"].dropna()
                result["price_history"] = closes

                # RSI (14)
                delta = closes.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - 100 / (1 + rs)
                result["rsi"] = rsi.iloc[-1]

                # SMA
                result["sma50"]  = closes.rolling(50).mean().iloc[-1]
                result["sma200"] = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None
                result["current_price"] = closes.iloc[-1]

                # 3-month momentum
                if len(closes) >= 63:
                    result["momentum_3m"] = closes.iloc[-1] / closes.iloc[-63] - 1
                else:
                    result["momentum_3m"] = None

                # 52-week range position
                hi52 = closes.max()
                lo52 = closes.min()
                result["range_pct"] = (closes.iloc[-1] - lo52) / (hi52 - lo52) if hi52 != lo52 else 0.5
            else:
                result["rsi"] = None
                result["sma50"] = None
                result["sma200"] = None
                result["current_price"] = result["price"]
                result["momentum_3m"] = None
                result["range_pct"] = None
        except Exception as e:
            logger.debug(f"{ticker} technical error: {e}")

        # override price if we have it from history
        if result.get("current_price"):
            result["price"] = result["current_price"]

        # extra info fields
        result["pe_trailing"] = safe_get(info, "trailingPE")
        result["pe_forward"]  = safe_get(info, "forwardPE")
        result["peg"]         = safe_get(info, "pegRatio")
        result["revenue_growth"] = safe_get(info, "revenueGrowth")
        result["gross_margin"]   = safe_get(info, "grossMargins")
        result["op_margin"]      = safe_get(info, "operatingMargins")
        result["shares_out"]     = safe_get(info, "sharesOutstanding")
        result["52w_high"]       = safe_get(info, "fiftyTwoWeekHigh")
        result["52w_low"]        = safe_get(info, "fiftyTwoWeekLow")
        result["beta"]           = safe_get(info, "beta")
        result["description"]    = safe_get(info, "longBusinessSummary", default="")[:300]

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"{ticker} fetch error: {e}")

    return result


def score_stock(d: dict) -> dict:
    """Return score dict with per-criterion scores and total."""
    scores = {}

    # 1. EPS CAGR (25 pts) ─────────────────────────────────────────
    eps = d.get("eps_cagr")
    if eps is None:
        scores["eps"] = 0
    elif eps >= 0.20:
        scores["eps"] = 25
    elif eps >= 0.15:
        scores["eps"] = 20
    elif eps >= 0.10:
        scores["eps"] = 15
    elif eps >= 0.05:
        scores["eps"] = 8
    else:
        scores["eps"] = 0

    # 2. ROIC (20 pts) ─────────────────────────────────────────────
    roic = d.get("roic")
    if roic is None:
        scores["roic"] = 0
    elif roic >= 0.30:
        scores["roic"] = 20
    elif roic >= 0.20:
        scores["roic"] = 16
    elif roic >= 0.15:
        scores["roic"] = 12
    elif roic >= 0.10:
        scores["roic"] = 6
    else:
        scores["roic"] = 0

    # 3. FCF / Net Income (15 pts) ─────────────────────────────────
    fcf_r = d.get("fcf_to_netinc")
    if fcf_r is None:
        scores["fcf"] = 7  # neutral when unavailable
    elif fcf_r >= 0.90:
        scores["fcf"] = 15
    elif fcf_r >= 0.75:
        scores["fcf"] = 12
    elif fcf_r >= 0.50:
        scores["fcf"] = 8
    elif fcf_r >= 0.20:
        scores["fcf"] = 4
    else:
        scores["fcf"] = 0

    # 4. Dilution (15 pts) ─────────────────────────────────────────
    dil = d.get("dilution_annual")
    if dil is None:
        scores["dilution"] = 7  # neutral
    elif dil <= -0.01:          # buybacks
        scores["dilution"] = 15
    elif dil <= 0.005:          # essentially flat
        scores["dilution"] = 13
    elif dil <= 0.01:
        scores["dilution"] = 10
    elif dil <= 0.02:
        scores["dilution"] = 6
    elif dil <= 0.03:
        scores["dilution"] = 3
    else:
        scores["dilution"] = 0

    # 5. Momentum (15 pts) ─────────────────────────────────────────
    mom = d.get("momentum_3m")
    sma50  = d.get("sma50")
    sma200 = d.get("sma200")
    price  = d.get("price") or d.get("current_price")

    mom_score = 0
    if mom is not None:
        if 0.0 <= mom <= 0.25:      # healthy uptrend, not parabolic
            mom_score += 10
        elif mom > 0.25:            # extended — still positive but risky
            mom_score += 5
        elif mom >= -0.10:          # mild pullback — potential entry
            mom_score += 7
        else:
            mom_score += 0

    if price and sma50 and price > sma50:
        mom_score += 3
    if price and sma200 and price > sma200:
        mom_score += 2
    scores["momentum"] = min(mom_score, 15)

    # 6. RSI positioning (10 pts) ──────────────────────────────────
    rsi = d.get("rsi")
    if rsi is None:
        scores["rsi"] = 5
    elif 45 <= rsi <= 65:       # sweet spot
        scores["rsi"] = 10
    elif 35 <= rsi < 45:        # oversold — entry signal
        scores["rsi"] = 9
    elif 65 < rsi <= 75:        # mildly overbought
        scores["rsi"] = 6
    elif rsi > 75:              # very overbought
        scores["rsi"] = 2
    else:                       # RSI < 35 — weak
        scores["rsi"] = 3

    total = sum(scores.values())
    scores["total"] = total
    return scores
