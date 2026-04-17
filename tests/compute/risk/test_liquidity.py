import numpy as np
import pandas as pd
import pytest

from compute.risk.liquidity import LiquidityParams, estimate_ewma_vol


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
