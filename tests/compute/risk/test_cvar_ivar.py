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


from unittest.mock import patch, MagicMock
from datetime import datetime

from compute.risk.var import portfolio_ivar


def _mock_result(div=10.0, undiv=12.0, uncorr=8.0, ids=('A', 'B')):
    """Создаёт заглушку возвращаемого значения portfolio_historical/parametric."""
    return {
        'diversified': div,
        'undiversified': undiv,
        'uncorrelated': uncorr,
        'individual_vars': {iid: 5.0 for iid in ids},
        'pnl_matrix': pd.DataFrame(),
        'corr_matrix': pd.DataFrame(),
    }


def _make_instrument(iid):
    inst = MagicMock()
    inst.instrument_id = iid
    return inst


def test_portfolio_ivar_two_instruments():
    """IVaR_A = var_full - var_without_A, IVaR_B = var_full - var_without_B."""
    inst_a = _make_instrument('A')
    inst_b = _make_instrument('B')
    instruments = [inst_a, inst_b]
    var_full = 10.0

    # без A: осталось [B] → diversified = 7.0
    # без B: осталось [A] → diversified = 6.0
    side_effects = [_mock_result(div=7.0, ids=('B',)), _mock_result(div=6.0, ids=('A',))]

    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31)

    with patch('compute.risk.var.portfolio_historical', side_effect=side_effects) as mock_hist:
        result = portfolio_ivar(
            dataProvider=None,
            instruments=instruments,
            calc_start=start,
            calc_end=end,
            confidence_level=0.95,
            window=252,
            horizon=1,
            method='historical',
            recommended_var_type='diversified',
            var_full=var_full,
        )
        assert mock_hist.call_count == 2

    assert result['A'] == pytest.approx(10.0 - 7.0)
    assert result['B'] == pytest.approx(10.0 - 6.0)


def test_portfolio_ivar_single_instrument_gives_full_var():
    """Портфель из 1 инструмента: подпортфель без него пуст → IVaR = var_full."""
    inst_a = _make_instrument('A')
    var_full = 5.0

    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31)

    with patch('compute.risk.var.portfolio_historical') as mock_hist:
        result = portfolio_ivar(
            dataProvider=None,
            instruments=[inst_a],
            calc_start=start,
            calc_end=end,
            confidence_level=0.95,
            window=252,
            horizon=1,
            method='historical',
            recommended_var_type='diversified',
            var_full=var_full,
        )
        mock_hist.assert_not_called()  # пустой подпортфель → без вызова

    assert result['A'] == pytest.approx(5.0)

def test_compute_cvar_raises_on_missing_var_key():
    """ValueError если individual_vars не покрывает все колонки pnl_matrix."""
    pnl = pd.DataFrame({'A': [0.01, -0.02, 0.03], 'B': [0.02, -0.01, 0.01]})
    with pytest.raises(ValueError, match="VaR"):
        compute_cvar(pnl, {'A': 0.05})  # 'B' отсутствует
