import numpy as np
import pandas as pd
import pytest

from compute.risk.liquidity import LiquidityParams, estimate_ewma_vol, estimate_spread_series
from instruments.BaseInstrument import Direction


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
