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
    """DataProvider mock returning constant-rate RUB curve (Svensson params)."""
    dates = pd.date_range("2024-06-01", periods=600, freq='D')
    dp = MagicMock()
    dp.get_curve_data.return_value = pd.DataFrame(
        {'B1': [rate * 10000] * 600, 'B2': [0] * 600, 'B3': [0] * 600,
         'T1': [1.0] * 600, 'G1': [0]*600, 'G2': [0]*600, 'G3': [0]*600,
         'G4': [0]*600, 'G5': [0]*600, 'G6': [0]*600, 'G7': [0]*600,
         'G8': [0]*600, 'G9': [0]*600},
        index=dates,
    )
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


def test_payer_receiver_are_opposite_signs(monkeypatch):
    """BUY (payer) and SELL (receiver) NPVs should sum to ~0."""
    import compute.pricers.swap_utils as su

    RATE = 0.20  # fixed_rate != discount rate -> non-zero NPV

    def mock_df_series(currency, tenor_series, curve_daily):
        r = pd.Series([0.16] * len(tenor_series), index=tenor_series.index)
        return (1.0 / (1.0 + r)) ** tenor_series

    monkeypatch.setattr(su, 'discount_factor_series', mock_df_series)

    dp = MagicMock()
    dp.get_curve_data.return_value = pd.DataFrame(
        {'dummy': [1.0] * 600},
        index=pd.date_range("2024-06-01", periods=600, freq='D'),
    )

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
