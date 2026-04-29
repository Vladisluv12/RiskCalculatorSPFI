"""
Standalone helpers for reading liquidity CSV files.
No DataProvider dependency — safe to call directly from UI.
"""

import os
import pandas as pd


def list_liquidity_files(data_dir: str) -> list[str]:
    """Return names of .csv files in {data_dir}/liquidity/."""
    liquidity_dir = os.path.join(data_dir, "liquidity")
    if not os.path.exists(liquidity_dir):
        return []
    return sorted(f for f in os.listdir(liquidity_dir) if f.lower().endswith(".csv"))


def liquidity_dir_path(data_dir: str) -> str:
    return os.path.join(data_dir, "liquidity")


def load_liquidity_csv(filepath) -> pd.DataFrame:
    """
    Read a liquidity CSV (path or file-like object).
    Normalises column names and computes spread_pct.
    Expected columns: date, ticker, bid, ask.

    spread_pct = (ask - bid) / abs(mid)  — absolute value of mid guards
    against zero or negative rates (e.g. IRS with negative fixing).
    Rows where mid == 0 are kept but spread_pct is set to NaN.
    """
    df = pd.read_csv(filepath, sep=";")
    df.columns = df.columns.str.strip().str.lower()

    for col in ("bid", "ask"):
        df[col] = df[col].astype(str).str.replace(",", ".").astype(float)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    mid = (df["ask"] + df["bid"]) / 2
    abs_mid = mid.abs().replace(0, float("nan"))
    df["spread_pct"] = (df["ask"] - df["bid"]) / abs_mid
    return df


def load_index(liquidity_dir: str) -> dict[str, str]:
    """Read index.csv → {ticker: batch_filename}."""
    index_path = os.path.join(liquidity_dir, "index.csv")
    if not os.path.exists(index_path):
        return {}
    df = pd.read_csv(index_path)
    if not {"ticker", "filename"}.issubset(df.columns):
        return {}
    return dict(zip(df["ticker"], df["filename"]))


def _needed_ticker_prefixes(instruments: list) -> list[str]:
    """Derive ticker prefix patterns needed for the given portfolio instruments."""
    from instruments.IRSwap import InterestRateSwap

    prefixes = []
    for inst in instruments:
        if isinstance(inst, InterestRateSwap):
            currency = inst.currency.value
            prefixes.append(f"{currency}_OIS_")
            prefixes.append(f"{currency}_IRS_")
        elif hasattr(inst, "currency_pair"):
            pair = inst.currency_pair.value.replace("/", "")
            prefixes.append(f"{pair}_")
    return prefixes


def load_for_portfolio(
    liquidity_dir: str,
    instruments: list,
) -> pd.DataFrame:
    """Load only batch files relevant to the current portfolio instruments.

    Returns combined DataFrame with columns: date, ticker, bid, ask, spread_pct.
    Returns empty DataFrame if index.csv is missing or no match found.
    """
    index = load_index(liquidity_dir)
    if not index:
        return pd.DataFrame()

    prefixes = _needed_ticker_prefixes(instruments)
    needed_files: set[str] = set()
    for ticker, filename in index.items():
        if any(ticker.startswith(p) for p in prefixes):
            needed_files.add(filename)

    if not needed_files:
        return pd.DataFrame()

    frames = []
    for filename in sorted(needed_files):
        path = os.path.join(liquidity_dir, filename)
        if os.path.exists(path):
            frames.append(load_liquidity_csv(path))

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
