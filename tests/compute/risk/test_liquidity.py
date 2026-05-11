import numpy as np
import pandas as pd
import pytest

from compute.modelling.liquidity import (
    LiquidityParams, estimate_ewma_vol, estimate_spread_series, compute_lc,
    estimate_irs_spread_series, compute_irs_lc,
)
from instruments.enums import Direction


def test_ewma_vol_positive():
    """EWMA-волатильность всегда положительна на ненулевых доходностях."""
    returns = pd.Series([0.01, -0.02, 0.015, -0.005, 0.03] * 10)
    result = estimate_ewma_vol(returns, lambda_=0.94)
    assert (result > 0).all()
    assert len(result) == len(returns)


def test_ewma_vol_low_lambda_reacts_faster():
    """Низкий λ даёт больший вес последним наблюдениям → spike в конце виден лучше."""
    returns = pd.Series([0.001] * 50 + [0.1])  # spike в конце
    vol_low = estimate_ewma_vol(returns, lambda_=0.50)
    vol_high = estimate_ewma_vol(returns, lambda_=0.99)
    assert vol_low.iloc[-1] > vol_high.iloc[-1]


def test_liquidity_params_defaults():
    params = LiquidityParams()
    assert params.k == 3.0
    assert params.floor_spread == 0.001
    assert params.alpha == 0.10
    assert params.lambda_ == 0.94
    assert params.avg_daily_volume == {}


def test_spread_series_floor():
    """При почти нулевой волатильности спред не падает ниже floor_spread."""
    returns = pd.Series([0.0001] * 100)
    params = LiquidityParams(k=3.0, floor_spread=0.002, alpha=0.0, lambda_=0.94)
    result = estimate_spread_series(
        fx_returns=returns, tenor_years=0.1,
        direction=Direction.BUY, notional=100.0,
        currency_pair='USD/RUB', params=params,
    )
    assert (result >= 0.002).all()


def test_spread_series_buy_gt_sell():
    """BUY-направление даёт больший спред, чем SELL (асимметрия рынка РФ)."""
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.standard_normal(100) * 0.01)
    params = LiquidityParams(k=3.0, floor_spread=0.001, alpha=0.10, lambda_=0.94)
    buy = estimate_spread_series(returns, 1.0, Direction.BUY, 100.0, 'USD/RUB', params)
    sell = estimate_spread_series(returns, 1.0, Direction.SELL, 100.0, 'USD/RUB', params)
    assert (buy > sell).all()


def test_spread_series_size_adj():
    """Большой номинал относительно ADV увеличивает спред."""
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.standard_normal(50) * 0.01)
    params_no_adv = LiquidityParams(k=3.0, floor_spread=0.001, alpha=0.0, lambda_=0.94)
    params_with_adv = LiquidityParams(
        k=3.0, floor_spread=0.001, alpha=0.0, lambda_=0.94,
        avg_daily_volume={'USD/RUB': 1_000.0},
    )
    base = estimate_spread_series(returns, 1.0, Direction.BUY, 500.0, 'USD/RUB', params_no_adv)
    sized = estimate_spread_series(returns, 1.0, Direction.BUY, 500.0, 'USD/RUB', params_with_adv)
    # size_adj = 1 + 0.5*(500/1000) = 1.25 > 1.0
    assert (sized > base).all()


def test_compute_lc_normal_formula():
    """LC_normal = 0.5 × |mid_pv| × s%_last."""
    spread_series = pd.Series([0.02] * 20)
    result = compute_lc(mid_pv=1_000.0, spread_series=spread_series, z_alpha=1.645)
    assert result['normal'] == pytest.approx(0.5 * 1_000.0 * 0.02)


def test_compute_lc_stressed_gt_normal():
    """LC_stressed > LC_normal при ненулевой дисперсии спреда."""
    rng = np.random.default_rng(7)
    spread_series = pd.Series(rng.uniform(0.01, 0.04, 50))
    result = compute_lc(mid_pv=1_000.0, spread_series=spread_series, z_alpha=1.645)
    assert result['stressed'] > result['normal']


def test_compute_lc_negative_pv():
    """Берётся |mid_pv|: отрицательный PV даёт тот же LC."""
    spread_series = pd.Series([0.02] * 20)
    pos = compute_lc(mid_pv=1_000.0, spread_series=spread_series, z_alpha=1.645)
    neg = compute_lc(mid_pv=-1_000.0, spread_series=spread_series, z_alpha=1.645)
    assert pos['normal'] == pytest.approx(neg['normal'])
    assert pos['stressed'] == pytest.approx(neg['stressed'])


from unittest.mock import MagicMock, patch
from datetime import datetime

from compute.risk.lvar import portfolio_lvar
from compute.modelling.liquidity import LiquidityParams
from instruments.enums import Direction, CurrencyPair
from instruments.FXForward import CurrencyForwardContract


def _make_forward(iid='FWD1', notional=1_000_000.0, direction=Direction.BUY):
    return CurrencyForwardContract(
        instrument_id=iid,
        notional=notional,
        direction=direction,
        start_date=datetime(2024, 6, 1),
        end_date=datetime(2024, 12, 31),
        currency_pair=CurrencyPair.USD_RUB,
        base_currency='USD',
        quote_currency='RUB',
        forward_rate=90.0,
    )


def test_portfolio_lvar_t1_factor_is_one():
    """При T=1 делитель = 1.0 → LVaR_normal = VaR + LC_normal."""
    rng = np.random.default_rng(0)
    n = 252
    dates = pd.date_range('2023-01-01', periods=n, freq='B')
    mock_curs = pd.DataFrame({'curs': rng.normal(85, 1, n)}, index=dates)
    mock_pv = pd.Series(rng.normal(50_000, 5_000, n), index=dates, name='FWD1')

    mock_dp = MagicMock()
    mock_dp.get_currency_data.return_value = mock_curs

    params = LiquidityParams(k=3.0, floor_spread=0.001, alpha=0.10, lambda_=0.94)

    with patch('compute.risk.lvar._get_pv_series', return_value=mock_pv):
        result = portfolio_lvar(
            instruments=[_make_forward()],
            dataProvider=mock_dp,
            calc_start=datetime(2023, 1, 1),
            calc_end=datetime(2023, 12, 31),
            params=params,
            T=1,
            confidence_level=0.95,
            window=252,
        )

    assert result['t_factor'] == pytest.approx(1.0)
    assert result['lvar_normal'] == pytest.approx(
        result['var_portfolio_abs'] + result['lc_total']['normal']
    )
    assert result['lvar_stressed'] >= result['lvar_normal']


def test_portfolio_lvar_t5_reduces_lvar():
    """При T=5 LVaR_T < LVaR_T1 (знаменатель > 1)."""
    rng = np.random.default_rng(1)
    n = 252
    dates = pd.date_range('2023-01-01', periods=n, freq='B')
    mock_curs = pd.DataFrame({'curs': rng.normal(85, 1, n)}, index=dates)
    mock_pv = pd.Series(rng.normal(50_000, 5_000, n), index=dates, name='FWD1')

    mock_dp = MagicMock()
    mock_dp.get_currency_data.return_value = mock_curs
    params = LiquidityParams(k=3.0, floor_spread=0.001, alpha=0.10, lambda_=0.94)

    with patch('compute.risk.lvar._get_pv_series', return_value=mock_pv):
        r1 = portfolio_lvar(
            instruments=[_make_forward()],
            dataProvider=mock_dp, calc_start=datetime(2023, 1, 1),
            calc_end=datetime(2023, 12, 31), params=params,
            T=1, confidence_level=0.95, window=252,
        )
        r5 = portfolio_lvar(
            instruments=[_make_forward()],
            dataProvider=mock_dp, calc_start=datetime(2023, 1, 1),
            calc_end=datetime(2023, 12, 31), params=params,
            T=5, confidence_level=0.95, window=252,
        )

    assert r5['lvar_normal'] < r1['lvar_normal']
    assert r5['t_factor'] == pytest.approx(np.sqrt((1+5)*(1+10)/(6*5)))


def test_liquidity_params_irs_defaults():
    params = LiquidityParams()
    assert params.k_irs == 3.0
    assert params.floor_spread_bps == 2.0
    assert params.observed_spreads_irs == {}


def test_compute_irs_lc_normal_formula():
    spread_series = pd.Series([5.0, 5.0, 6.0, 5.5, 5.0])
    result = compute_irs_lc(dv01=1000.0, spread_series_bps=spread_series, z_alpha=1.645)
    assert result['normal'] == pytest.approx(0.5 * 1000.0 * 5.0)
    assert result['stressed'] >= result['normal']


def test_compute_irs_lc_stressed_formula():
    spread_series = pd.Series([4.0, 5.0, 6.0, 5.0, 5.0])
    result = compute_irs_lc(dv01=2000.0, spread_series_bps=spread_series, z_alpha=1.645)
    sigma = float(spread_series.std())
    expected_stressed = 0.5 * 2000.0 * (5.0 + 1.645 * sigma)
    assert result['stressed'] == pytest.approx(expected_stressed, rel=1e-6)


def test_estimate_irs_spread_series_floor():
    rate_changes = pd.Series([0.0] * 30)
    params = LiquidityParams(k_irs=3.0, floor_spread_bps=2.0)
    result = estimate_irs_spread_series(
        rate_changes_bps=rate_changes, tenor_years=5.0,
        direction=Direction.BUY, params=params,
    )
    assert (result >= 2.0).all()


def test_estimate_irs_spread_series_buy_gt_sell():
    rng = np.random.default_rng(42)
    rate_changes = pd.Series(rng.normal(0, 5, 50))
    params = LiquidityParams(k_irs=3.0, floor_spread_bps=2.0, alpha=0.10)
    buy = estimate_irs_spread_series(
        rate_changes_bps=rate_changes, tenor_years=5.0,
        direction=Direction.BUY, params=params,
    )
    sell = estimate_irs_spread_series(
        rate_changes_bps=rate_changes, tenor_years=5.0,
        direction=Direction.SELL, params=params,
    )
    assert (buy > sell).all()


def test_estimate_irs_spread_series_override_scalar():
    # alpha=0 → отключаем direction-adjustment, чтобы override возвращался «как есть».
    params = LiquidityParams(observed_spreads_irs={'IRS1': 10.0}, alpha=0.0)
    rate_changes = pd.Series([1.0] * 10)
    result = estimate_irs_spread_series(
        rate_changes_bps=rate_changes, tenor_years=5.0,
        direction=Direction.BUY, params=params,
        instrument_id='IRS1',
    )
    assert (result == 10.0).all()


from instruments.IRSwap import InterestRateSwap
from instruments.enums import (
    Currency, DayCountConvention, FloatingIndex, OffsetRule, PaymentTiming,
)


def _make_irs_instrument(iid='IRS1'):
    return InterestRateSwap(
        instrument_id=iid,
        notional=100_000_000.0,
        direction=Direction.BUY,
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2028, 1, 1),
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


def test_portfolio_lvar_irs_lc_nonzero():
    """IRS должен давать LC > 0 при наличии ставочной волатильности."""
    rng = np.random.default_rng(7)
    n = 252
    dates = pd.date_range('2023-01-01', periods=n, freq='B')

    mock_pv = pd.Series(rng.normal(500_000, 50_000, n), index=dates, name='price')

    ois_row_values = {
        '1w': 7.0, '1m': 7.5, '3m': 8.0, '6m': 8.5,
        '1y': 9.0, '2y': 9.5, '3y': 10.0, '5y': 10.5, '7y': 11.0, '10y': 11.5,
    }
    ois_df = pd.DataFrame([ois_row_values], index=[dates[-1]])

    fixing_values = rng.normal(0.165, 0.001, n)
    fixing_df = pd.DataFrame({'fixing': fixing_values}, index=dates)

    mock_dp = MagicMock()
    mock_dp.get_ois_curve_data.return_value = ois_df
    mock_dp.get_fixing_data.return_value = fixing_df

    params = LiquidityParams(k_irs=3.0, floor_spread_bps=2.0, alpha=0.10, lambda_=0.94)

    with patch('compute.risk.lvar._get_pv_series', return_value=mock_pv):
        result = portfolio_lvar(
            instruments=[_make_irs_instrument()],
            dataProvider=mock_dp,
            calc_start=datetime(2023, 1, 1),
            calc_end=datetime(2023, 12, 29),
            params=params,
            T=1,
            confidence_level=0.95,
            window=252,
        )

    lc = result['instrument_lc']['IRS1']
    assert lc['normal'] > 0.0
    assert lc['stressed'] >= lc['normal']
    assert 's_bps' in lc


def test_portfolio_lvar_irs_lc_override():
    """observed_spreads_irs override должен подставлять заданный спред (с alpha=0 — без direction-adjustment)."""
    rng = np.random.default_rng(9)
    n = 50
    dates = pd.date_range('2023-01-01', periods=n, freq='B')
    mock_pv = pd.Series(rng.normal(500_000, 10_000, n), index=dates, name='price')

    ois_row_values = {
        '1w': 7.0, '1m': 7.5, '3m': 8.0, '6m': 8.5,
        '1y': 9.0, '2y': 9.5, '3y': 10.0, '5y': 10.5, '7y': 11.0, '10y': 11.5,
    }
    ois_df = pd.DataFrame([ois_row_values], index=[dates[-1]])
    fixing_df = pd.DataFrame({'fixing': [7.5] * n}, index=dates)

    mock_dp = MagicMock()
    mock_dp.get_ois_curve_data.return_value = ois_df
    mock_dp.get_fixing_data.return_value = fixing_df

    params = LiquidityParams(
        k_irs=3.0, floor_spread_bps=2.0,
        observed_spreads_irs={'IRS1': 8.0},
        alpha=0.0,
    )

    with patch('compute.risk.lvar._get_pv_series', return_value=mock_pv):
        result = portfolio_lvar(
            instruments=[_make_irs_instrument()],
            dataProvider=mock_dp,
            calc_start=datetime(2023, 1, 1),
            calc_end=datetime(2023, 3, 17),
            params=params,
            T=1,
            confidence_level=0.95,
            window=50,
        )

    assert result['instrument_lc']['IRS1']['s_bps'] == pytest.approx(8.0)
