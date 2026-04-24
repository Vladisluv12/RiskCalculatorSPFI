"""
Generates data/liquidity/liquidity.csv on first startup if the file doesn't exist.

Reads historical FX prices, applies EWMA volatility to derive daily neutral base spreads
for each (currency_pair, product_type, tenor_bucket) combination. Tenor buckets represent
typical FX forward/swap maturities. The spread scales with sqrt(tenor_years) as in the
parametric model.
"""

import csv
import os

import numpy as np
import pandas as pd

from compute.modelling.liquidity import estimate_ewma_vol

_K = 3.0
_FLOOR = 0.001
_LAMBDA = 0.94

_TICKERS = ["USDRUB", "EURRUB", "CNYRUB", "EURUSD"]
_PRODUCTS = ["FXForward", "FXSwap"]
# Typical FX forward/swap tenor buckets in days → years
_TENORS: list[tuple[str, float]] = [
    ("7D",   7   / 365),
    ("30D",  30  / 365),
    ("90D",  90  / 365),
    ("180D", 180 / 365),
    ("365D", 1.0),
]


def _load_mid_series(currency_dir: str, ticker: str) -> pd.Series | None:
    filepath = os.path.join(currency_dir, f"{ticker}.csv")
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath, sep=";", encoding="utf-8-sig", decimal=",")
    if df.empty or "data" not in df.columns or "curs" not in df.columns:
        return None
    df["_date"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_date"]).set_index("_date").sort_index()
    nominal = int(df["nominal"].iloc[0]) if "nominal" in df.columns else 1
    mid = df["curs"].astype(str).str.replace(",", ".").astype(float) / nominal
    return mid.rename("mid")


def ensure_liquidity_file(data_dir: str) -> str:
    """Create data/liquidity/liquidity.csv if it doesn't exist. Returns the file path."""
    liquidity_dir = os.path.join(data_dir, "liquidity")
    os.makedirs(liquidity_dir, exist_ok=True)

    output_path = os.path.join(liquidity_dir, "liquidity.csv")
    if os.path.exists(output_path):
        return output_path

    currency_dir = os.path.join(data_dir, "currency")
    rows = []

    for pair in _TICKERS:
        mid = _load_mid_series(currency_dir, pair)
        if mid is None or len(mid) < 2:
            continue

        fx_returns = np.log(mid / mid.shift(1)).dropna()
        sigma_ewma = estimate_ewma_vol(fx_returns, _LAMBDA)
        mid_aligned = mid.reindex(sigma_ewma.index)

        for tenor_label, tenor_years in _TENORS:
            spread_pct = np.maximum(
                _K * sigma_ewma * np.sqrt(max(tenor_years, 1 / 365)),
                _FLOOR,
            )
            half = spread_pct / 2
            bid = (mid_aligned * (1 - half)).round(4)
            ask = (mid_aligned * (1 + half)).round(4)

            for product in _PRODUCTS:
                ticker = f"{pair}_{product}_{tenor_label}"
                for date, b, a in zip(sigma_ewma.index, bid.values, ask.values):
                    rows.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "ticker": ticker,
                        "bid": b,
                        "ask": a,
                    })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "ticker", "bid", "ask"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    return output_path
