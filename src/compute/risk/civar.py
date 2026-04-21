import pandas as pd
import numpy as np
from datetime import datetime
from compute.risk.portfolio_var import portfolio_historical, portfolio_parametric
from utils.DataProvider import DataProvider


def portfolio_ivar(
    dataProvider: DataProvider,
    instruments: list,
    calc_start: datetime,
    calc_end: datetime,
    confidence_level: float = 0.95,
    window: int = 252,
    horizon: int = 1,
    method: str = 'historical',
    recommended_var_type: str = 'diversified',
    var_full: float = 0.0,
) -> dict:
    """
    Incremental VaR: IVaR_i = VaR_portfolio_full - VaR_portfolio_without_i.
    var_full передаётся снаружи (уже вычислен на странице), поэтому
    функция делает ровно N вызовов приценщика (по одному на подпортфель).
    """
    _portfolio_fn = portfolio_historical if method == 'historical' else portfolio_parametric
    result = {}
    for i, inst in enumerate(instruments):
        sub_instruments = [ins for j, ins in enumerate(instruments) if j != i]
        if not sub_instruments:
            var_without = 0.0
        else:
            sub_result = _portfolio_fn(
                dataProvider,
                sub_instruments,
                calc_start,
                calc_end,
                confidence_level=confidence_level,
                window=window,
                horizon=horizon,
            )
            var_without = sub_result[f"{recommended_var_type}_var"]
        result[inst.instrument_id] = var_full - var_without
    return result

def compute_cvar(pnl_matrix: pd.DataFrame, individual_vars: dict) -> dict:
    """
    Component VaR: CVaR_i = ρ(pnl_i, pnl_portfolio) · VaR_i.
    Может быть отрицательным для хеджирующих позиций.
    Σ CVaR_i ≈ диверсифицированный VaR портфеля.
    Если портфельный PnL вырожден (нулевая дисперсия), корреляция считается
    относительно портфеля без данного инструмента.
    """
    portfolio_pnl = pnl_matrix.sum(axis=1)
    missing = set(pnl_matrix.columns) - set(individual_vars.keys())
    if missing:
        raise ValueError(f'Отсутствуют VaR-значения для колонок: {missing}')
    result = {}
    for col in pnl_matrix.columns:
        rho = float(pnl_matrix[col].corr(portfolio_pnl))
        if np.isnan(rho):
            other_cols = [c for c in pnl_matrix.columns if c != col]
            if other_cols:
                other_pnl = pnl_matrix[other_cols].sum(axis=1)
                rho = float(pnl_matrix[col].corr(other_pnl))
            if np.isnan(rho):
                rho = 0.0
        result[col] = rho * individual_vars[col]
    return result