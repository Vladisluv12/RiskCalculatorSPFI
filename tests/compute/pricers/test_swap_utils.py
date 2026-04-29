import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch
from compute.pricers.swap_utils import (
    generate_payment_schedule, year_fraction, discount_factor_series,
    ibor_forward_rate,
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

def test_discount_factor_series_with_ten_percent(monkeypatch):
    import compute.pricers.swap_utils as su
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    tenor_series = pd.Series([1.0, 1.0, 1.0], index=dates)
    mock_r = pd.DataFrame({'rf_rate': [0.10, 0.10, 0.10]}, index=dates)
    monkeypatch.setattr(su, 'get_risk_free_rate', lambda *a, **kw: mock_r)

    result = su.discount_factor_series('RUB', tenor_series, pd.DataFrame(index=dates))

    expected = 1.0 / (1.10 ** 1.0)
    assert abs(result.iloc[0] - expected) < 1e-10
    assert len(result) == 3


def test_discount_factor_decreases_with_tenor(monkeypatch):
    import compute.pricers.swap_utils as su
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    tenor_series = pd.Series([1.0, 2.0], index=dates)
    mock_r = pd.DataFrame({'rf_rate': [0.10, 0.10]}, index=dates)
    monkeypatch.setattr(su, 'get_risk_free_rate', lambda *a, **kw: mock_r)

    result = su.discount_factor_series('RUB', tenor_series, pd.DataFrame(index=dates))
    assert result.iloc[0] > result.iloc[1]


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


# --- ibor_forward_rate ---

def test_ibor_forward_rate_flat_curve():
    # Flat 10% ZC: P(0.5) = 1/1.1^0.5, P(1.0) = 1/1.1
    # L = (P(0.5)/P(1.0) - 1) / 0.5 = (1.1^0.5 - 1) / 0.5
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    tenor_start = pd.Series([0.5, 0.5, 0.5], index=dates)
    tenor_end   = pd.Series([1.0, 1.0, 1.0], index=dates)
    dcf = 0.5

    def mock_rfr(currency, tenors, curve):
        return pd.DataFrame({'rf_rate': [0.10] * len(tenors)}, index=tenors.index)

    with patch('compute.pricers.swap_utils.get_risk_free_rate', side_effect=mock_rfr):
        result = ibor_forward_rate('EUR', tenor_start, tenor_end, dcf, pd.DataFrame(index=dates))

    p1 = 1.0 / 1.1 ** 0.5
    p2 = 1.0 / 1.1 ** 1.0
    expected = (p1 / p2 - 1.0) / dcf
    assert abs(result.iloc[0] - expected) < 1e-10


def test_ibor_forward_rate_upward_curve_exceeds_long_spot():
    # r(1y)=5%, r(2y)=6% → 1y forward starting in 1y should exceed 6%
    dates = pd.date_range("2024-01-01", periods=1)
    tenor_start = pd.Series([1.0], index=dates)
    tenor_end   = pd.Series([2.0], index=dates)
    dcf = 1.0

    call_results = [
        pd.DataFrame({'rf_rate': [0.05]}, index=dates),  # r(1y)
        pd.DataFrame({'rf_rate': [0.06]}, index=dates),  # r(2y)
    ]
    call_iter = iter(call_results)

    with patch('compute.pricers.swap_utils.get_risk_free_rate', side_effect=lambda *a, **kw: next(call_iter)):
        result = ibor_forward_rate('EUR', tenor_start, tenor_end, dcf, pd.DataFrame(index=dates))

    # P(1y)/P(2y) = (1/1.05) / (1/1.06^2) = 1.06^2 / 1.05
    expected = (1.06 ** 2 / 1.05 - 1.0) / 1.0
    assert abs(result.iloc[0] - expected) < 1e-6
    assert result.iloc[0] > 0.06


def test_ibor_forward_rate_zero_dcf_raises():
    dates = pd.date_range("2024-01-01", periods=1)
    tenor_start = pd.Series([0.5], index=dates)
    tenor_end   = pd.Series([1.0], index=dates)
    import pytest
    
    def mock_rfr(currency, tenors, curve):
        return pd.DataFrame({'rf_rate': [0.05] * len(tenors)}, index=tenors.index)
    
    with patch('compute.pricers.swap_utils.get_risk_free_rate', side_effect=mock_rfr):
        with pytest.raises(ValueError, match="dcf must be positive"):
            ibor_forward_rate('EUR', tenor_start, tenor_end, 0.0, pd.DataFrame(index=dates))


# --- ibor_forward_rate_with_basis ---

from compute.pricers.swap_utils import ibor_forward_rate_with_basis


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
