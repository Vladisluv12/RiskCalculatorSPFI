"""
Generate IRS/OIS bid/ask time series from historical fixings.

Model: s_bps(t) = max(k × σ_rate_bps(t) × √tenor_years, floor_spread_bps)
bid = mid_rate - s_bps/2 / 10_000
ask = mid_rate + s_bps/2 / 10_000

Ticker format: {CURRENCY}_{TYPE}_{INDEX}_{tenor}Y
  TYPE  = OIS for overnight-compounded indices, IRS for term/key-rate indices
Examples: RUB_OIS_RUONIA_2Y, EUR_IRS_EURIBOR3M_5Y, USD_OIS_SOFR_1Y

Output: src/data/liquidity/irs_liquidity.csv  (date;ticker;bid;ask)
"""

import os
import numpy as np
import pandas as pd

K_IRS = 3.0
FLOOR_BPS = 2.0
LAMBDA = 0.94
TENORS_Y = [1, 2, 3, 5, 7, 10]

# (currency, inst_type, index_label, fixing_filename)
_SOURCES = [
    # OIS-based indices
    ("RUB", "OIS", "RUONIA",      "RUONIA Avg..csv"),
    ("EUR", "OIS", "ESTR",        "ESTR_Comp.csv"),
    ("USD", "OIS", "SOFR",        "SOFR_Comp.csv"),
    ("CNY", "OIS", "RUSFARCNY",   "RUSFARCNY_Comp.csv"),
    # IRS (term/key-rate) indices
    ("EUR", "IRS", "EURIBOR1M",   "Euribor_EUR_1m.csv"),
    ("EUR", "IRS", "EURIBOR3M",   "Euribor_EUR_3m.csv"),
    ("EUR", "IRS", "EURIBOR6M",   "Euribor_EUR_6m.csv"),
    ("RUB", "IRS", "RUSFAR3M",    "RUSFAR RUB 3m.csv"),
    ("RUB", "IRS", "RUSFARON",    "RusFar RUB O_N.csv"),
    ("RUB", "IRS", "KEYRATE",     "RUB KeyRate.csv"),
]


def _load_fixing(path: str) -> pd.Series:
    df = pd.read_csv(path, sep=",")
    df.columns = df.columns.str.strip()
    date_col = next(c for c in df.columns if "дат" in c.lower() or "date" in c.lower())
    val_col = next(c for c in df.columns if c != date_col)
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col].astype(str).str.replace(",", "."), errors="coerce")
    series = df.dropna().set_index(date_col)[val_col].sort_index()
    series = series[series != 0]  # drop zero fixings — they yield mid=0 → spread_pct=Inf
    return series / 100  # percent → fraction  # percent → fraction


def _ewma_vol_bps(rate_series: pd.Series) -> pd.Series:
    changes_bps = rate_series.diff().dropna() * 10_000
    alpha = 1.0 - LAMBDA
    return changes_bps.pow(2).ewm(alpha=alpha, adjust=False).mean().apply(np.sqrt)


def generate(data_dir: str) -> pd.DataFrame:
    fixings_dir = os.path.join(data_dir, "fixings")
    rows = []

    for currency, inst_type, index_label, fname in _SOURCES:
        fpath = os.path.join(fixings_dir, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP {currency}/{inst_type}/{index_label}: {fname} not found")
            continue

        fixing = _load_fixing(fpath)
        sigma_bps = _ewma_vol_bps(fixing)
        mid = fixing.reindex(sigma_bps.index)

        for tenor_y in TENORS_Y:
            ticker = f"{currency}_{inst_type}_{index_label}_{tenor_y}Y"
            s_bps = np.maximum(K_IRS * sigma_bps * np.sqrt(tenor_y), FLOOR_BPS)
            half = s_bps / 2 / 10_000
            chunk = pd.DataFrame({
                "date":   sigma_bps.index.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "bid":    (mid - half).round(6).values,
                "ask":    (mid + half).round(6).values,
            })
            rows.append(chunk)

        print(f"  {currency}/{inst_type}/{index_label}: {len(fixing)} fixings → {len(TENORS_Y)} tenors")

    if not rows:
        raise RuntimeError("No fixing data found; check src/data/fixings/")

    return pd.concat(rows, ignore_index=True).sort_values(["ticker", "date"])


def main():
    src_dir = os.path.join(os.path.dirname(__file__), "..")
    data_dir = os.path.join(src_dir, "data")
    out_path = os.path.join(data_dir, "liquidity", "irs_liquidity.csv")

    print("Generating IRS/OIS liquidity bid/ask...")
    df = generate(data_dir)
    df.to_csv(out_path, sep=";", index=False)
    print(f"\nSaved {len(df):,} rows → {os.path.abspath(out_path)}")
    print("Tickers:")
    for t in sorted(df["ticker"].unique()):
        print(f"  {t}")


if __name__ == "__main__":
    main()
