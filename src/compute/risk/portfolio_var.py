import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
from compute.pricers.CurrencySwapPricer import CurrencySwapPricer
from compute.pricers.ForwardPricer import ForwardPricer
from compute.risk.var import _resolve_target_column
from instruments.BaseInstrument import BaseInstrument
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from utils.DataProvider import DataProvider


def portfolio_historical_es(dataProvider: DataProvider, instruments: list, calc_start: datetime, calc_end: datetime, confidence_level: float = 0.95, window: int = 252, horizon: int = 1) -> float:
    """
    Исторический ES для портфеля: ES по агрегированному PnL (сумма позиций).
    """
    series_list = [_get_pnl_series(dataProvider, inst, calc_start, calc_end, window) for inst in instruments]
    raw = pd.concat(series_list, axis=1)
    raw = raw[~raw.index.duplicated(keep='last')]
    pnl_matrix = _deduplicate_columns(raw).dropna()
    if pnl_matrix.empty:
        raise ValueError('Нет общих дат для расчёта ES портфеля.')
    portfolio_pnl = pnl_matrix.sum(axis=1) * np.sqrt(max(1, horizon))
    alpha = 1 - confidence_level
    var_cutoff = float(portfolio_pnl.quantile(alpha))
    tail = portfolio_pnl[portfolio_pnl <= var_cutoff]
    if tail.empty:
        raise ValueError('Хвост PnL портфеля пуст — недостаточно данных для расчёта ES.')
    return abs(float(tail.mean()))


def portfolio_parametric_es(dataProvider: DataProvider, instruments: list, calc_start: datetime, calc_end: datetime, confidence_level: float = 0.95, window: int = 252, horizon: int = 1) -> float:
    """
    Параметрический ES для портфеля
    """
    series_list = [_get_pnl_series(dataProvider, inst, calc_start, calc_end, window) for inst in instruments]
    raw = pd.concat(series_list, axis=1)
    raw = raw[~raw.index.duplicated(keep='last')]
    pnl_matrix = _deduplicate_columns(raw).dropna()
    if pnl_matrix.empty:
        raise ValueError('Нет общих дат для расчёта ES портфеля.')
    portfolio_pnl = pnl_matrix.sum(axis=1)
    alpha = 1 - confidence_level
    z_alpha = norm.ppf(alpha)
    es_1d = -portfolio_pnl.mean() + portfolio_pnl.std() * norm.pdf(z_alpha) / alpha
    es_h = float(es_1d) * np.sqrt(max(1, horizon))
    if np.isnan(es_h):
        raise ValueError('NaN при расчёте параметрического ES портфеля.')
    return abs(float(es_h))


def _deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Делает имена колонок уникальными, добавляя суффикс _2, _3, ... при дублях."""
    seen: dict = {}
    new_cols = []
    for col in df.columns:
        if col not in seen:
            seen[col] = 1
            new_cols.append(col)
        else:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
    df = df.copy()
    df.columns = new_cols
    return df


def _get_pv_series(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, window: int) -> pd.Series:
    """Возвращает сырой ряд PV (без преобразований), последние window точек."""
    returns = pd.DataFrame()
    if isinstance(instrument, CurrencyForwardContract):
        returns = ForwardPricer(365).calculate_pv(instrument, dataProvider, calc_start, calc_end)
    elif isinstance(instrument, CurrencySwapContract):
        returns = CurrencySwapPricer(365).calculate_pv(instrument, dataProvider, calc_start, calc_end)
    if returns.empty:
        raise ValueError(f'Не удалось получить историю PV для {instrument.instrument_id}.')
    target_col = _resolve_target_column(returns)
    return returns[target_col].tail(min(window, len(returns))).rename(instrument.instrument_id)


def _get_pnl_series(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, window: int) -> pd.Series:
    """Возвращает pct_change PnL-серию для одного инструмента (используется в ES и individual VaR)."""
    pv = _get_pv_series(dataProvider, instrument, calc_start, calc_end, window)
    pnl = pv.pct_change().dropna()
    if pnl.empty:
        raise ValueError(f'История доходностей пуста для {instrument.instrument_id}.')
    return pnl


def portfolio_historical(dataProvider: DataProvider, instruments: list, calc_start: datetime, calc_end: datetime, confidence_level: float=0.95, window: int=252, horizon: int=1) -> dict:
    """\n    Исторический VaR для портфеля.\n\n    Возвращает словарь с ключами:\n      pnl_matrix       — DataFrame, столбец = инструмент\n      individual_vars  — dict {id: VaR}\n      corr_matrix      — матрица корреляций\n      diversified_var  — sqrt(VaR^T · R · VaR)\n      undiversified_var — sum(VaR_i)\n      uncorrelated_var  — sqrt(sum(VaR_i^2))\n    """
    pv_list = []
    for inst in instruments:
        pv_list.append(_get_pv_series(dataProvider, inst, calc_start, calc_end, window))
    raw = pd.concat(pv_list, axis=1)
    raw = raw[~raw.index.duplicated(keep='last')]
    pv_matrix = _deduplicate_columns(raw).dropna()
    if pv_matrix.empty:
        raise ValueError('Нет общих дат для построения матрицы PnL портфеля.')

    # pct_change — для VaR (относительные доходности)
    pnl_matrix = pv_matrix.pct_change().dropna()
    # diff — для корреляции (абсолютные изменения PV, не искажённые делением на ≈0)
    diff_matrix = pv_matrix.diff().dropna()

    scale = np.sqrt(max(1, horizon))
    pnl_matrix = pnl_matrix * scale
    alpha = 1 - confidence_level
    individual_vars = {col: abs(float(pnl_matrix[col].quantile(alpha))) for col in pnl_matrix.columns}
    corr_matrix = diff_matrix.corr()
    var_vec = np.array([individual_vars[col] for col in pnl_matrix.columns])
    diversified_var = float(np.sqrt(var_vec @ corr_matrix.values @ var_vec))
    undiversified_var = float(var_vec.sum())
    uncorrelated_var = float(np.sqrt((var_vec ** 2).sum()))
    return {'pnl_matrix': pnl_matrix, 'individual_vars': individual_vars, 'corr_matrix': corr_matrix, 'diversified_var': diversified_var, 'undiversified_var': undiversified_var, 'uncorrelated_var': uncorrelated_var}


def portfolio_parametric(dataProvider: DataProvider, instruments: list, calc_start: datetime, calc_end: datetime, confidence_level: float=0.95, window: int=252, horizon: int=1) -> dict:
    """\n    Параметрический VaR для портфеля.\n\n    Возвращает тот же набор ключей, что portfolio_historical.\n    """
    pv_list = []
    for inst in instruments:
        pv_list.append(_get_pv_series(dataProvider, inst, calc_start, calc_end, window))
    raw = pd.concat(pv_list, axis=1)
    raw = raw[~raw.index.duplicated(keep='last')]
    pv_matrix = _deduplicate_columns(raw).dropna()
    if pv_matrix.empty:
        raise ValueError('Нет общих дат для построения матрицы PnL портфеля.')

    pnl_matrix = pv_matrix.pct_change().dropna()
    diff_matrix = pv_matrix.diff().dropna()

    z_score = norm.ppf(confidence_level)
    scale = np.sqrt(max(1, horizon))
    individual_vars = {}
    for col in pnl_matrix.columns:
        s = pnl_matrix[col]
        v = abs((-s.mean() + s.std() * z_score) * scale)
        if np.isnan(v):
            raise ValueError(f'NaN при расчете параметрического VaR для {col}.')
        individual_vars[col] = float(v)
    corr_matrix = diff_matrix.corr()
    var_vec = np.array([individual_vars[col] for col in pnl_matrix.columns])
    diversified_var = float(np.sqrt(var_vec @ corr_matrix.values @ var_vec))
    undiversified_var = float(var_vec.sum())
    uncorrelated_var = float(np.sqrt((var_vec ** 2).sum()))
    return {'pnl_matrix': pnl_matrix, 'individual_vars': individual_vars, 'corr_matrix': corr_matrix, 'diversified_var': diversified_var, 'undiversified_var': undiversified_var, 'uncorrelated_var': uncorrelated_var}

