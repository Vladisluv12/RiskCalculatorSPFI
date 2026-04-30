import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
from compute.risk.var import _get_pv_series
from utils.DataProvider import DataProvider
from compute.modelling.liquidity import (
    LiquidityParams, estimate_spread_series, compute_lc,
    estimate_irs_spread_series, compute_irs_lc,
)
from compute.pricers.swap_utils import irs_dv01
from instruments.IRSwap import InterestRateSwap


def portfolio_lvar(
    instruments: list,
    dataProvider: DataProvider,
    calc_start: datetime,
    calc_end: datetime,
    params : LiquidityParams,
    T: int = 1,
    confidence_level: float = 0.95,
    window: int = 252,
) -> dict:
    """
    LVaR для портфеля.

    Возвращает:
      instrument_lc  — dict {id: {'normal': float, 'stressed': float}}
      lc_total       — {'normal': float, 'stressed': float}
      lvar_normal    — float: (VaR + LC_normal) / t_factor
      lvar_stressed  — float: (VaR + LC_stressed) / t_factor
      t_factor       — float: √((1+T)(1+2T)/(6T))
    """
    if T < 1:
        raise ValueError(f"T must be >= 1, got {T}")

    z_alpha = float(norm.ppf(confidence_level))
    t_factor = float(np.sqrt((1 + T) * (1 + 2 * T) / (6 * T)))

    instrument_lc: dict = {}
    pv_series_list: list = []  # для расчёта абсолютного портфельного VaR

    for inst in instruments:
        if isinstance(inst, InterestRateSwap):
            try:
                pv_series = _get_pv_series(dataProvider, inst, calc_start, calc_end, window)
                mid_pv = float(pv_series.iloc[-1])
                pv_series_list.append(pv_series)
            except Exception:
                mid_pv = 0.0

            currency = inst.currency.value
            try:
                ois_data = dataProvider.get_ois_curve_data(currency, calc_start, calc_end)
                ois_row = ois_data[ois_data.index <= pd.Timestamp(calc_end)].iloc[-1]
                dv01 = irs_dv01(inst, ois_row, calc_end)
            except Exception:
                instrument_lc[inst.instrument_id] = {
                    'normal': 0.0, 'stressed': 0.0, 's_bps': 0.0, 'abs_pv': abs(mid_pv),
                }
                continue

            try:
                fixing_df = dataProvider.get_fixing_data(inst.floating_index, calc_start, calc_end)
                rate_changes_bps = fixing_df['fixing'].diff().dropna().tail(window) * 10_000
            except Exception:
                rate_changes_bps = pd.Series(dtype=float)

            if rate_changes_bps.empty:
                instrument_lc[inst.instrument_id] = {
                    'normal': 0.0, 'stressed': 0.0, 's_bps': 0.0, 'abs_pv': abs(mid_pv),
                }
                continue

            calc_end_ts = pd.Timestamp(calc_end)
            tenor_years = max(1.0 / 365, (pd.Timestamp(inst.end_date) - calc_end_ts).days / 365)

            spread_series_bps = estimate_irs_spread_series(
                rate_changes_bps=rate_changes_bps,
                tenor_years=tenor_years,
                direction=inst.direction,
                params=params,
                instrument_id=inst.instrument_id,
                notional=float(inst.notional),
                currency=inst.currency.value,
            )

            lc = compute_irs_lc(dv01=dv01, spread_series_bps=spread_series_bps, z_alpha=z_alpha)
            lc['s_bps'] = float(spread_series_bps.iloc[-1])
            lc['abs_pv'] = abs(mid_pv)
            instrument_lc[inst.instrument_id] = lc
            continue

        pair_ticker = inst.currency_pair.value.replace('/', '')  # 'USDRUB'
        pair_label = inst.currency_pair.value                    # 'USD/RUB'

        try:
            currency_df = dataProvider.get_currency_data(pair_ticker, calc_start, calc_end)
        except Exception:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        if currency_df.empty:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        fx_returns = currency_df['curs'].pct_change().dropna().tail(window)

        calc_end_ts = pd.Timestamp(calc_end)
        end_dt_ts = pd.Timestamp(inst.end_date)
        tenor_years = max(1 / 365, (end_dt_ts - calc_end_ts).days / 365)

        try:
            pv_series = _get_pv_series(dataProvider, inst, calc_start, calc_end, window)
            mid_pv = float(pv_series.iloc[-1])
        except Exception:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        pv_series_list.append(pv_series)

        spread_series = estimate_spread_series(
            fx_returns=fx_returns,
            tenor_years=tenor_years,
            direction=inst.direction,
            notional=float(inst.notional),
            currency_pair=pair_label,
            params=params,
            instrument_id=inst.instrument_id,
        )

        lc = compute_lc(mid_pv=mid_pv, spread_series=spread_series, z_alpha=z_alpha)
        lc['s_pct'] = float(spread_series.iloc[-1])
        lc['abs_pv'] = abs(mid_pv)
        instrument_lc[inst.instrument_id] = lc

    lc_total_normal = sum(v['normal'] for v in instrument_lc.values())
    lc_total_stressed = sum(v['stressed'] for v in instrument_lc.values())
    total_abs_pv = sum(v.get('abs_pv', 0.0) for v in instrument_lc.values())

    # Абсолютный VaR портфеля — через diff() суммарного PV (а не pct_change)
    if pv_series_list:
        portfolio_pv = pd.concat(pv_series_list, axis=1).dropna().sum(axis=1)
        portfolio_diff = portfolio_pv.diff().dropna().tail(window)
        alpha = 1.0 - confidence_level
        var_portfolio_abs = float(abs(np.percentile(portfolio_diff, alpha * 100)))
    else:
        var_portfolio_abs = 0.0

    return {
        'instrument_lc': instrument_lc,
        'lc_total': {'normal': lc_total_normal, 'stressed': lc_total_stressed},
        'var_portfolio_abs': var_portfolio_abs,
        'total_abs_pv': total_abs_pv,
        'lvar_normal': (var_portfolio_abs + lc_total_normal) / t_factor,
        'lvar_stressed': (var_portfolio_abs + lc_total_stressed) / t_factor,
        't_factor': t_factor,
    }
