"""
CSV spread matching utilities for the LVaR page.
Maps portfolio instruments to bid/ask spread series from a liquidity CSV file.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

_TENOR_BUCKETS = [7, 30, 90, 180, 365]
_PRODUCT_MAP = {"CurrencyForwardContract": "FXForward", "CurrencySwapContract": "FXSwap"}


def build_observed_spreads(liquidity_df: pd.DataFrame, instruments: list, calc_end: datetime) -> dict:
    """Match each instrument to the best (pair, product, tenor) ticker in the CSV.

    Returns observed_spreads keyed by instrument_id -> pd.Series or float spread_pct.
    """
    has_date = "date" in liquidity_df.columns
    result = {}

    for inst in instruments:
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


def liquidity_spreads_key(liquidity_source: str, csv_label: str) -> tuple:
    """Build a hashable key representing current CSV spread data (for stale detection)."""
    if liquidity_source != csv_label:
        return ()
    liq_df = st.session_state.get("lvar_liquidity_df")
    if liq_df is None:
        return ()
    if "date" in liq_df.columns:
        return (
            len(liq_df),
            str(liq_df["date"].min()),
            str(liq_df["date"].max()),
            tuple(sorted(liq_df["ticker"].unique())),
        )
    return tuple(sorted((row["ticker"], row["spread_pct"]) for _, row in liq_df.iterrows()))
