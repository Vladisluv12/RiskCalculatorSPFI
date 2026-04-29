"""
CSV spread matching utilities for the LVaR page.
Maps portfolio instruments to bid/ask spread series from a liquidity CSV file.
"""

from datetime import datetime

from instruments.IRSwap import InterestRateSwap

import pandas as pd
import streamlit as st

_TENOR_BUCKETS = [7, 30, 90, 180, 365]
_PRODUCT_MAP = {"CurrencyForwardContract": "FXForward", "CurrencySwapContract": "FXSwap"}


def build_observed_spreads(liquidity_df: pd.DataFrame, instruments: list, calc_end: datetime) -> dict:
    """Match each FX instrument to the best (pair, product, tenor) ticker in the CSV.

    Returns observed_spreads keyed by instrument_id -> pd.Series or float spread_pct.
    IRS instruments are skipped here; use build_observed_spreads_irs for them.
    """
    has_date = "date" in liquidity_df.columns
    result = {}

    for inst in instruments:
        if not hasattr(inst, "currency_pair"):
            continue
        pair = inst.currency_pair.value.replace("/", "")
        product_code = _PRODUCT_MAP.get(type(inst).__name__, "FXForward")
        tenor_days = max(1, (pd.Timestamp(inst.end_date) - pd.Timestamp(calc_end)).days)
        closest_tenor = min(_TENOR_BUCKETS, key=lambda t: abs(t - tenor_days))

        candidates = [f"{pair}_{product_code}_{closest_tenor}D"]
        for other_tenor in sorted(_TENOR_BUCKETS, key=lambda t: abs(t - tenor_days)):
            candidates.append(f"{pair}_{product_code}_{other_tenor}D")
            candidates.append(f"{pair}_FXForward_{other_tenor}D")

        matched_grp = None
        for cand in candidates:
            grp = liquidity_df[liquidity_df["ticker"] == cand]
            if not grp.empty:
                matched_grp = grp
                break
        if matched_grp is None:
            fallback = liquidity_df[liquidity_df["ticker"].str.startswith(pair + "_")]
            matched_grp = fallback if not fallback.empty else None

        if matched_grp is None or matched_grp.empty:
            continue

        if has_date:
            result[inst.instrument_id] = matched_grp.set_index("date")["spread_pct"].sort_index()
        else:
            result[inst.instrument_id] = float(matched_grp["spread_pct"].iloc[-1])

    return result


_IRS_TENOR_BUCKETS = [1, 2, 3, 5, 7, 10]

# Maps FloatingIndex.name → (inst_type, index_label) matching generate_irs_liquidity.py
_INDEX_META: dict[str, tuple[str, str]] = {
    "RUONIA_AVG":      ("OIS", "RUONIA"),
    "RUONIA_COMP":     ("OIS", "RUONIA"),
    "ESTR_COMP":       ("OIS", "ESTR"),
    "SOFR_COMP":       ("OIS", "SOFR"),
    "RUSFARCNY_COMP":  ("OIS", "RUSFARCNY"),
    "EURIBOR_EUR_1M":  ("IRS", "EURIBOR1M"),
    "EURIBOR_EUR_3M":  ("IRS", "EURIBOR3M"),
    "EURIBOR_EUR_6M":  ("IRS", "EURIBOR6M"),
    "RUSFAR_RUB_3M":   ("IRS", "RUSFAR3M"),
    "RUSFAR_RUB_ON":   ("IRS", "RUSFARON"),
    "RUB_KEY_RATE":    ("IRS", "KEYRATE"),
}


def build_observed_spreads_irs(
    liquidity_df: pd.DataFrame, instruments: list, calc_end: datetime
) -> dict:
    """Match each IRS/OIS instrument to the closest-tenor ticker in the CSV.

    Ticker format: {CURRENCY}_{OIS|IRS}_{INDEX}_{tenor}Y
      e.g. RUB_OIS_RUONIA_2Y, EUR_IRS_EURIBOR3M_5Y

    s_bps is recovered as (ask - bid) * 10_000.

    Returns {instrument_id: pd.Series or float} in bps for
    LiquidityParams.observed_spreads_irs.
    """
    irs_mask = liquidity_df["ticker"].str.contains(r"_(?:OIS|IRS)_", regex=True, na=False)
    irs_df = liquidity_df[irs_mask].copy()
    if irs_df.empty:
        return {}

    has_date = "date" in irs_df.columns
    irs_df = irs_df.assign(s_bps=(irs_df["ask"] - irs_df["bid"]) * 10_000)
    result = {}

    for inst in instruments:
        if not isinstance(inst, InterestRateSwap):
            continue

        currency = inst.currency.value
        meta = _INDEX_META.get(inst.floating_index.name)
        inst_type, index_label = meta if meta else ("OIS", "")

        tenor_days = max(1, (pd.Timestamp(inst.end_date) - pd.Timestamp(calc_end)).days)
        tenor_years = tenor_days / 365

        matched_grp = None
        for t in sorted(_IRS_TENOR_BUCKETS, key=lambda t: abs(t - tenor_years)):
            exact = f"{currency}_{inst_type}_{index_label}_{t}Y"
            grp = irs_df[irs_df["ticker"] == exact]
            if not grp.empty:
                matched_grp = grp
                break

        if matched_grp is None or matched_grp.empty:
            # fallback: any ticker for this currency+type
            pattern = f"{currency}_{inst_type}_"
            fallback = irs_df[irs_df["ticker"].str.startswith(pattern)]
            matched_grp = fallback if not fallback.empty else None

        if matched_grp is None or matched_grp.empty:
            continue

        if has_date and matched_grp["date"].notna().any():
            result[inst.instrument_id] = (
                matched_grp.groupby("date")["s_bps"].mean().sort_index()
            )
        else:
            result[inst.instrument_id] = float(matched_grp["s_bps"].mean())

    return result


def liquidity_spreads_key(liquidity_source: str, csv_label: str) -> tuple:
    """Build a hashable cache key for the current liquidity data."""
    if liquidity_source != csv_label:
        return ()
    liq_df = st.session_state.get("lvar_liquidity_df")
    if liq_df is None or liq_df.empty:
        return ()
    tickers = tuple(sorted(liq_df["ticker"].unique()))
    n_rows = len(liq_df)
    if "date" in liq_df.columns:
        return (n_rows, str(liq_df["date"].min()), str(liq_df["date"].max()), tickers)
    return (n_rows, tickers)
