import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pytest
import pandas as pd
from datetime import datetime
from compute.pricers.swap_utils import (
    generate_payment_schedule, year_fraction,
)
from instruments.enums import DayCountConvention, FloatingIndex, OffsetRule, PaymentTiming


# --- generate_payment_schedule ---

def test_end_of_period_returns_single_end_date():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2025, 1, 1), PaymentTiming.END_OF_PERIOD
    )
    assert result == [datetime(2025, 1, 1)]


def test_quarterly_schedule_four_dates():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2025, 1, 1), PaymentTiming.QUARTERLY
    )
    from dateutil.relativedelta import relativedelta
    expected = [
        datetime(2024, 1, 1) + relativedelta(months=3),
        datetime(2024, 1, 1) + relativedelta(months=6),
        datetime(2024, 1, 1) + relativedelta(months=9),
        datetime(2025, 1, 1),
    ]
    assert result == expected


def test_annually_schedule_three_years():
    result = generate_payment_schedule(
        datetime(2022, 1, 1), datetime(2025, 1, 1), PaymentTiming.ANNUALLY
    )
    assert len(result) == 3
    assert result[-1] == datetime(2025, 1, 1)


def test_semi_annually_schedule():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2025, 1, 1), PaymentTiming.SEMI_ANNUALLY
    )
    assert len(result) == 2
    assert result[-1] == datetime(2025, 1, 1)


def test_monthly_schedule_twelve_dates():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2025, 1, 1), PaymentTiming.MONTHLY
    )
    assert len(result) == 12
    assert result[-1] == datetime(2025, 1, 1)


def test_last_date_is_always_end():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2024, 5, 15), PaymentTiming.QUARTERLY
    )
    assert result[-1] == datetime(2024, 5, 15)


# --- year_fraction ---

def test_act_360_ninety_one_days():
    yf = year_fraction(datetime(2024, 1, 1), datetime(2024, 4, 1), DayCountConvention.ACT_360)
    assert abs(yf - 91 / 360) < 1e-10


def test_act_365_ninety_one_days():
    yf = year_fraction(datetime(2024, 1, 1), datetime(2024, 4, 1), DayCountConvention.ACT_365)
    assert abs(yf - 91 / 365) < 1e-10


def test_30e_360_full_year():
    yf = year_fraction(datetime(2024, 1, 1), datetime(2025, 1, 1), DayCountConvention._30E_360)
    assert abs(yf - 1.0) < 1e-10


def test_act_act_full_leap_year():
    yf = year_fraction(datetime(2024, 1, 1), datetime(2025, 1, 1), DayCountConvention.ACT_ACT)
    assert abs(yf - 1.0) < 1e-10


def test_act_act_spans_two_years():
    yf = year_fraction(datetime(2024, 1, 1), datetime(2025, 7, 1), DayCountConvention.ACT_ACT)
    assert 1.0 < yf < 2.0


# --- discount_factor_series ---


# --- offset_rule in generate_payment_schedule ---

def test_offset_none_leaves_date_unchanged():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2024, 7, 1),
        PaymentTiming.END_OF_PERIOD, OffsetRule.NONE
    )
    assert result == [datetime(2024, 7, 1)]


def test_offset_one_day_advances_by_one_business_day():
    # 2024-03-28 is Thursday -> +1 BD = Friday 2024-03-29
    result = generate_payment_schedule(
        datetime(2023, 9, 28), datetime(2024, 3, 28),
        PaymentTiming.END_OF_PERIOD, OffsetRule.ONE_DAY
    )
    assert result == [datetime(2024, 3, 29)]


def test_offset_one_day_skips_weekend():
    # 2024-03-29 is Friday -> +1 BD = Monday 2024-04-01
    result = generate_payment_schedule(
        datetime(2023, 9, 29), datetime(2024, 3, 29),
        PaymentTiming.END_OF_PERIOD, OffsetRule.ONE_DAY
    )
    assert result == [datetime(2024, 4, 1)]


def test_offset_two_days_advances_by_two_business_days():
    # 2024-03-28 is Thursday -> +2 BD = Monday 2024-04-01
    result = generate_payment_schedule(
        datetime(2023, 9, 28), datetime(2024, 3, 28),
        PaymentTiming.END_OF_PERIOD, OffsetRule.TWO_DAYS
    )
    assert result == [datetime(2024, 4, 1)]


def test_offset_default_is_none_backward_compat():
    result = generate_payment_schedule(
        datetime(2024, 1, 1), datetime(2025, 1, 1), PaymentTiming.QUARTERLY
    )
    assert len(result) == 4
    assert result[-1] == datetime(2025, 1, 1)


def test_offset_none_leaves_weekend_date_unchanged():
    # 2024-03-30 is Saturday — NONE must not adjust it
    result = generate_payment_schedule(
        datetime(2023, 9, 30), datetime(2024, 3, 30),
        PaymentTiming.END_OF_PERIOD, OffsetRule.NONE
    )
    assert result == [datetime(2024, 3, 30)]


def test_offset_one_day_from_saturday_gives_monday():
    # 2024-03-30 is Saturday → +1 BD from Saturday = Monday 2024-04-01
    result = generate_payment_schedule(
        datetime(2023, 9, 30), datetime(2024, 3, 30),
        PaymentTiming.END_OF_PERIOD, OffsetRule.ONE_DAY
    )
    assert result == [datetime(2024, 4, 1)]


def test_offset_two_days_from_saturday_gives_tuesday():
    # Saturday 2024-03-30: roll to Monday 2024-04-01 (counts as 1st BD), +1 more BD = Tuesday 2024-04-02
    result = generate_payment_schedule(
        datetime(2023, 9, 30), datetime(2024, 3, 30),
        PaymentTiming.END_OF_PERIOD, OffsetRule.TWO_DAYS
    )
    assert result == [datetime(2024, 4, 2)]


# --- ibor_forward_rate_with_basis ---

from compute.pricers.swap_utils import ibor_forward_rate_with_basis, irs_dv01
from instruments.IRSwap import InterestRateSwap
from instruments.enums import Currency, Direction


def _make_flat_ois_daily(rate_pct: float, n: int = 3) -> pd.DataFrame:
    """Flat OIS DataFrame for testing (all tenors = rate_pct %)."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    cols = ["1w", "1m", "3m", "6m", "1y", "2y", "3y", "5y", "7y", "10y"]
    return pd.DataFrame({c: [rate_pct] * n for c in cols}, index=dates)


def test_ibor_forward_with_basis_zero_basis():
    # Flat 4% OIS, fixing = 4% → basis = 0 → forward = ois_forward ≈ 4%
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    tenor_start = pd.Series([0.25, 0.25, 0.25], index=dates)
    tenor_end   = pd.Series([0.50, 0.50, 0.50], index=dates)
    ois_daily = _make_flat_ois_daily(4.0, n=3)
    fixing_daily = pd.Series([0.04, 0.04, 0.04], index=dates)

    result = ibor_forward_rate_with_basis(
        FloatingIndex.EURIBOR_EUR_3M,
        tenor_start, tenor_end, 0.25, ois_daily, fixing_daily,
    )
    # OIS forward on flat 4% curve ≈ 4% (slight difference due to compounding vs simple)
    assert abs(result.iloc[0] - 0.04) < 0.001


def test_ibor_forward_with_basis_positive_basis_shifts_all_forwards():
    # fixing = 4.5%, OIS spot 3m = 4% → basis = +0.5%
    # All forwards should be ~0.5% above OIS forwards
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    tenor_start = pd.Series([0.25, 0.25, 0.25], index=dates)
    tenor_end   = pd.Series([0.50, 0.50, 0.50], index=dates)
    ois_daily = _make_flat_ois_daily(4.0, n=3)
    fixing_daily = pd.Series([0.045, 0.045, 0.045], index=dates)  # 4.5%

    result_with_basis = ibor_forward_rate_with_basis(
        FloatingIndex.EURIBOR_EUR_3M,
        tenor_start, tenor_end, 0.25, ois_daily, fixing_daily,
    )
    fixing_zero = pd.Series([0.04, 0.04, 0.04], index=dates)  # zero basis
    result_zero_basis = ibor_forward_rate_with_basis(
        FloatingIndex.EURIBOR_EUR_3M,
        tenor_start, tenor_end, 0.25, ois_daily, fixing_zero,
    )

    diff = result_with_basis.iloc[0] - result_zero_basis.iloc[0]
    assert abs(diff - 0.005) < 1e-6  # basis = exactly +0.5%


def test_ibor_forward_with_basis_rolling_smooths_spike():
    # Days 1-3: basis = +0.5%; day 4: basis spikes to +1.5%.
    # With basis_window=4: rolling mean on day 4 = (0.5+0.5+0.5+1.5)/4 = 0.75%
    # With basis_window=1: instantaneous basis on day 4 = 1.5%
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    tenor_start = pd.Series([0.25] * 4, index=dates)
    tenor_end   = pd.Series([0.50] * 4, index=dates)
    ois_daily = _make_flat_ois_daily(4.0, n=4)
    # OIS spot for EURIBOR 3M tenor (90/365) at 4% flat → fixing that gives +0.5% basis
    # We set ois_spot manually via fixing values (fixing = ois_spot + basis).
    # Since ois is flat 4%, ois_spot ≈ 0.04, so fixing = 0.045 gives basis=0.005
    fixing_daily = pd.Series([0.045, 0.045, 0.045, 0.055], index=dates)

    result_smoothed = ibor_forward_rate_with_basis(
        FloatingIndex.EURIBOR_EUR_3M,
        tenor_start, tenor_end, 0.25, ois_daily, fixing_daily,
        basis_window=4,
    )
    result_instant = ibor_forward_rate_with_basis(
        FloatingIndex.EURIBOR_EUR_3M,
        tenor_start, tenor_end, 0.25, ois_daily, fixing_daily,
        basis_window=1,
    )

    # Smoothed basis on last day must be less than instantaneous (spike damped)
    assert result_smoothed.iloc[-1] < result_instant.iloc[-1]
    # Smoothed value on last day ≈ 3/4 * 0.005 + 1/4 * 0.015 above the zero-basis forward
    smoothed_basis = (0.005 * 3 + 0.015) / 4
    instant_basis = 0.015
    assert abs(result_instant.iloc[-1] - result_smoothed.iloc[-1] - (instant_basis - smoothed_basis)) < 1e-6


def test_ibor_forward_with_basis_zero_dcf_raises():
    dates = pd.date_range("2024-01-01", periods=1)
    with pytest.raises(ValueError, match="dcf must be positive"):
        ibor_forward_rate_with_basis(
            FloatingIndex.EURIBOR_EUR_3M,
            pd.Series([0.25], index=dates),
            pd.Series([0.50], index=dates),
            0.0,
            _make_flat_ois_daily(4.0, n=1),
            pd.Series([0.04], index=dates),
        )


def _make_irs(start, end, notional=10_000_000.0):
    return InterestRateSwap(
        instrument_id='IRS_TEST',
        notional=notional,
        direction=Direction.BUY,
        start_date=start,
        end_date=end,
        currency=Currency.RUB,
        fixed_rate=0.10,
        fixed_day_count=DayCountConvention.ACT_365,
        fixed_payment_timing=PaymentTiming.QUARTERLY,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=FloatingIndex.RUONIA_COMP,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_365,
        floating_payment_timing=PaymentTiming.QUARTERLY,
        floating_offset_rule=OffsetRule.NONE,
    )


_OIS_ROW = pd.Series({
    '1w': 7.0, '1m': 7.5, '3m': 8.0, '6m': 8.5,
    '1y': 9.0, '2y': 9.5, '3y': 10.0, '5y': 10.5, '7y': 11.0, '10y': 11.5,
})


def test_irs_dv01_positive():
    contract = _make_irs(datetime(2024, 1, 1), datetime(2029, 1, 1))
    result = irs_dv01(contract, _OIS_ROW, calc_date=datetime(2024, 1, 1))
    assert result > 0.0


def test_irs_dv01_increases_with_tenor():
    short = irs_dv01(_make_irs(datetime(2024, 1, 1), datetime(2025, 1, 1)), _OIS_ROW, datetime(2024, 1, 1))
    long_ = irs_dv01(_make_irs(datetime(2024, 1, 1), datetime(2029, 1, 1)), _OIS_ROW, datetime(2024, 1, 1))
    assert long_ > short


def test_irs_dv01_scales_with_notional():
    small = irs_dv01(_make_irs(datetime(2024, 1, 1), datetime(2029, 1, 1), notional=1_000_000.0), _OIS_ROW, datetime(2024, 1, 1))
    large = irs_dv01(_make_irs(datetime(2024, 1, 1), datetime(2029, 1, 1), notional=10_000_000.0), _OIS_ROW, datetime(2024, 1, 1))
    assert large == pytest.approx(10 * small, rel=1e-9)


def test_irs_dv01_zero_past_maturity():
    contract = _make_irs(datetime(2020, 1, 1), datetime(2023, 1, 1))
    result = irs_dv01(contract, _OIS_ROW, calc_date=datetime(2024, 1, 1))
    assert result == 0.0
