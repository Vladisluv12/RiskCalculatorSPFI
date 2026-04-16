import numpy as np
import pandas as pd
import pytest

from compute.risk.var import compute_cvar


def _make_pnl(n=300, seed=42):
    """Два инструмента с высокой положительной корреляцией."""
    rng = np.random.default_rng(seed)
    a = pd.Series(rng.standard_normal(n), name='A')
    b = 0.8 * a + 0.2 * pd.Series(rng.standard_normal(n), name='noise')
    b.name = 'B'
    return pd.DataFrame({'A': a, 'B': b})


def test_compute_cvar_returns_all_keys():
    pnl = _make_pnl()
    individual_vars = {'A': 0.05, 'B': 0.04}
    result = compute_cvar(pnl, individual_vars)
    assert set(result.keys()) == {'A', 'B'}


def test_compute_cvar_values_are_floats():
    pnl = _make_pnl()
    individual_vars = {'A': 0.05, 'B': 0.04}
    result = compute_cvar(pnl, individual_vars)
    for v in result.values():
        assert isinstance(v, float)


def test_compute_cvar_hedging_instrument_is_negative():
    """Инструмент с идеальной отрицательной корреляцией → CVaR < 0."""
    rng = np.random.default_rng(0)
    a = pd.Series(rng.standard_normal(300), name='A')
    b = -a.copy()
    b.name = 'B'
    pnl = pd.DataFrame({'A': a, 'B': b})
    individual_vars = {'A': 0.05, 'B': 0.05}
    result = compute_cvar(pnl, individual_vars)
    assert result['B'] < 0, "Хеджирующий инструмент должен давать отрицательный CVaR"


def test_compute_cvar_sum_approximately_equals_portfolio_var():
    """Σ CVaR_i ≈ диверсифицированный VaR при нормальном распределении."""
    pnl = _make_pnl()
    portfolio_pnl = pnl.sum(axis=1)
    from scipy.stats import norm
    z = norm.ppf(0.95)
    individual_vars = {
        'A': float(abs(-pnl['A'].mean() + pnl['A'].std() * z)),
        'B': float(abs(-pnl['B'].mean() + pnl['B'].std() * z)),
    }
    result = compute_cvar(pnl, individual_vars)
    cvar_sum = sum(result.values())
    div_var = float(abs(-portfolio_pnl.mean() + portfolio_pnl.std() * z))
    assert abs(cvar_sum - div_var) / div_var < 0.15, (
        f"Σ CVaR ({cvar_sum:.4f}) слишком далеко от div VaR ({div_var:.4f})"
    )