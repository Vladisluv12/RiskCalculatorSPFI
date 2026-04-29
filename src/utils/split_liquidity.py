"""
One-time utility: merge liquidity.csv + irs_liquidity.csv into per-group batch
files and write index.csv.

Usage:
    cd src
    python utils/split_liquidity.py
"""
import os
import re
import pandas as pd

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "liquidity")


def _batch_name(ticker: str) -> str:
    """Derive batch filename from ticker string."""
    irs_match = re.match(r"^([A-Z]+_(?:OIS|IRS))_", ticker)
    if irs_match:
        return f"irs_{irs_match.group(1)}.csv"
    fx_pair = ticker.split("_")[0]
    return f"fx_{fx_pair}.csv"


def split(data_dir: str = _DATA_DIR) -> None:
    fx_path = os.path.join(data_dir, "liquidity.csv")
    irs_path = os.path.join(data_dir, "irs_liquidity.csv")

    frames = []
    for path in (fx_path, irs_path):
        if os.path.exists(path):
            df = pd.read_csv(path, sep=";")
            df.columns = df.columns.str.strip().str.lower()
            frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No source CSVs found in {data_dir}")

    merged = pd.concat(frames, ignore_index=True)
    merged["_batch"] = merged["ticker"].map(_batch_name)

    index_rows = (
        merged[["ticker", "_batch"]]
        .drop_duplicates("ticker")
        .rename(columns={"_batch": "filename"})
    )
    index_rows.to_csv(os.path.join(data_dir, "index.csv"), index=False)
    print(f"Wrote index.csv ({len(index_rows)} tickers)")

    for batch_file, group in merged.groupby("_batch"):
        out = group.drop(columns=["_batch"])
        out.to_csv(os.path.join(data_dir, batch_file), sep=";", index=False)
        size_mb = os.path.getsize(os.path.join(data_dir, batch_file)) / 1_048_576
        print(f"  {batch_file}: {len(out):,} rows, {size_mb:.1f} MB")


if __name__ == "__main__":
    split()
