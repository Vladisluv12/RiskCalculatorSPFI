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
    """
    df = pd.read_csv(filepath, sep=";")
    df.columns = df.columns.str.strip().str.lower()

    for col in ("bid", "ask"):
        df[col] = df[col].astype(str).str.replace(",", ".").astype(float)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["spread_pct"] = (df["ask"] - df["bid"]) / ((df["ask"] + df["bid"]) / 2)
    return df
