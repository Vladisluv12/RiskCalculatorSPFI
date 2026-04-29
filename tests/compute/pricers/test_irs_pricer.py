import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock

from instruments.IRSwap import InterestRateSwap
from instruments.enums import (
    Currency, DayCountConvention, PaymentTiming,
    OffsetRule, Direction, FloatingIndex
)
from compute.pricers.IRSPricer import IRSPricer


def _make_swap(
    fixed_rate=0.16,
    timing=PaymentTiming.END_OF_PERIOD,
    direction=Direction.BUY,
    start=datetime(2025, 1, 1),
    end=datetime(2026, 1, 1),
) -> InterestRateSwap:
    return InterestRateSwap(
        instrument_id='TEST-IRS',
        notional=1_000_000.0,
        direction=direction,
        start_date=start,
        end_date=end,
        currency=Currency.RUB,
        fixed_rate=fixed_rate,
        fixed_day_count=DayCountConvention.ACT_365,
        fixed_payment_timing=timing,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=FloatingIndex.RUONIA_COMP,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_365,
        floating_payment_timing=PaymentTiming.END_OF_PERIOD,
        floating_offset_rule=OffsetRule.NONE,
    )


def _make_mock_dp(rate=0.16):
    """DataProvider mock returning constant-rate RUB curve (Svensson params) and flat OIS."""
    dates = pd.date_range("2024-06-01", periods=600, freq='D')
    dp = MagicMock()
    dp.get_curve_data.return_value = pd.DataFrame(
        {'B1': [rate * 10000] * 600, 'B2': [0] * 600, 'B3': [0] * 600,
         'T1': [1.0] * 600, 'G1': [0]*600, 'G2': [0]*600, 'G3': [0]*600,
         'G4': [0]*600, 'G5': [0]*600, 'G6': [0]*600, 'G7': [0]*600,
         'G8': [0]*600, 'G9': [0]*600},
        index=dates,
    )
    rate_pct = rate * 100
    dp.get_ois_curve_data.return_value = pd.DataFrame({
        '1w': [rate_pct]*600, '1m': [rate_pct]*600, '3m': [rate_pct]*600,
        '6m': [rate_pct]*600, '1y': [rate_pct]*600, '2y': [rate_pct]*600,
        '3y': [rate_pct]*600, '5y': [rate_pct]*600, '7y': [rate_pct]*600,
        '10y': [rate_pct]*600,
    }, index=dates)
    return dp


def test_calculate_pv_returns_dataframe():
    swap = _make_swap()
    dp = _make_mock_dp()
    pricer = IRSPricer(365)
    result = pricer.calculate_pv(swap, dp, datetime(2025, 1, 1), datetime(2025, 6, 1))
    assert isinstance(result, pd.DataFrame)
    assert 'price' in result.columns


def test_calculate_pv_non_empty():
    swap = _make_swap()
    dp = _make_mock_dp()
    pricer = IRSPricer(365)
    result = pricer.calculate_pv(swap, dp, datetime(2025, 1, 1), datetime(2025, 6, 1))
    assert len(result) > 0


def test_calculate_pv_index_within_range():
    swap = _make_swap()
    dp = _make_mock_dp()
    pricer = IRSPricer(365)
    calc_start = datetime(2025, 1, 1)
    calc_end = datetime(2025, 6, 1)
    result = pricer.calculate_pv(swap, dp, calc_start, calc_end)
    assert result.index.min() >= pd.Timestamp(calc_start)
    assert result.index.max() <= pd.Timestamp(calc_end)


def test_payer_receiver_are_opposite_signs():
    """BUY (payer) and SELL (receiver) NPVs should sum to ~0."""

    RATE = 0.20  # fixed_rate != discount rate -> non-zero NPV

    _dates = pd.date_range("2024-06-01", periods=600, freq='D')
    dp = MagicMock()
    dp.get_curve_data.return_value = pd.DataFrame(
        {'dummy': [1.0] * 600},
        index=_dates,
    )
    _rate_pct = 16.0
    dp.get_ois_curve_data.return_value = pd.DataFrame({
        '1w': [_rate_pct]*600, '1m': [_rate_pct]*600, '3m': [_rate_pct]*600,
        '6m': [_rate_pct]*600, '1y': [_rate_pct]*600, '2y': [_rate_pct]*600,
        '3y': [_rate_pct]*600, '5y': [_rate_pct]*600, '7y': [_rate_pct]*600,
        '10y': [_rate_pct]*600,
    }, index=_dates)

    swap_buy = _make_swap(fixed_rate=RATE, direction=Direction.BUY)
    swap_sell = _make_swap(fixed_rate=RATE, direction=Direction.SELL)
    pricer = IRSPricer(365)

    r_buy = pricer.calculate_pv(swap_buy, dp, datetime(2025, 1, 1), datetime(2025, 3, 1))
    r_sell = pricer.calculate_pv(swap_sell, dp, datetime(2025, 1, 1), datetime(2025, 3, 1))

    npv_buy = r_buy['price'].iloc[0]
    npv_sell = r_sell['price'].iloc[0]
    assert abs(npv_buy + npv_sell) < 1.0  # sum should be ~0


def test_quarterly_produces_non_empty_result():
    dp = _make_mock_dp(rate=0.10)
    pricer = IRSPricer(365)
    swap_q = _make_swap(timing=PaymentTiming.QUARTERLY)
    r_q = pricer.calculate_pv(swap_q, dp, datetime(2025, 1, 1), datetime(2025, 3, 1))
    assert 'price' in r_q.columns
    assert len(r_q) > 0


def _make_euribor_swap(
    fixed_rate=0.04,
    start=datetime(2025, 1, 1),
    end=datetime(2026, 1, 1),
) -> InterestRateSwap:
    return InterestRateSwap(
        instrument_id='TEST-EURIBOR',
        notional=1_000_000.0,
        direction=Direction.BUY,
        start_date=start,
        end_date=end,
        currency=Currency.EUR,
        fixed_rate=fixed_rate,
        fixed_day_count=DayCountConvention.ACT_365,
        fixed_payment_timing=PaymentTiming.ANNUALLY,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=FloatingIndex.EURIBOR_EUR_3M,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_360,
        floating_payment_timing=PaymentTiming.QUARTERLY,
        floating_offset_rule=OffsetRule.NONE,
    )


def _make_eur_mock_dp():
    """DataProvider mock with flat 4% EUR ZC curve (ECB Nelson-Siegel params) and flat 4% OIS."""
    dates = pd.date_range("2024-06-01", periods=600, freq='D')
    dp = MagicMock()
    eur_curve = pd.DataFrame({
        'BETA0': [4.0] * 600, 'BETA1': [0.0] * 600,
        'BETA2': [0.0] * 600, 'BETA3': [0.0] * 600,
        'TAU1':  [1.0] * 600, 'TAU2':  [1.0] * 600,
    }, index=dates)
    ois_curve = pd.DataFrame({
        '1w': [4.0]*600, '1m': [4.0]*600, '3m': [4.0]*600,
        '6m': [4.0]*600, '1y': [4.0]*600, '2y': [4.0]*600,
        '3y': [4.0]*600, '5y': [4.0]*600, '7y': [4.0]*600, '10y': [4.0]*600,
    }, index=dates)
    dp.get_curve_data.return_value = eur_curve
    dp.get_ois_curve_data.return_value = ois_curve
    fixing_df = pd.DataFrame({'fixing': [4.0] * 600}, index=dates)  # 4% EURIBOR
    dp.get_fixing_data.return_value = fixing_df
    return dp


def test_euribor_swap_returns_nonempty_result():
    swap = _make_euribor_swap()
    dp = _make_eur_mock_dp()
    pricer = IRSPricer(365)
    result = pricer.calculate_pv(swap, dp, datetime(2025, 1, 1), datetime(2025, 6, 1))
    assert isinstance(result, pd.DataFrame)
    assert 'price' in result.columns
    assert len(result) > 0


def test_euribor_atm_swap_near_zero_npv():
    # Flat 4% ZC: IBOR forward ≈ 4%, fixed_rate=4% → NPV should be close to 0
    # Tolerance 5000 on 1M notional = 0.5% — flat curve approximation
    swap = _make_euribor_swap(fixed_rate=0.04)
    dp = _make_eur_mock_dp()
    pricer = IRSPricer(365)
    result = pricer.calculate_pv(swap, dp, datetime(2025, 1, 1), datetime(2025, 2, 1))
    assert result['price'].abs().max() < 5000
