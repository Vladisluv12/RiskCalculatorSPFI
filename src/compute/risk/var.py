import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
from instruments.BaseInstrument import BaseInstrument
from utils.DataProvider import DataProvider
from compute.pricers.pricer_dispatch import get_pv_series as _get_pv_dispatch


def to_pnl(returns):
    """\n    Преобразует цены в доходности (PnL).\n    """
    if returns.empty:
        return pd.DataFrame(dtype=float)
    else:
        return returns.pct_change().dropna()


def _resolve_target_column(df: pd.DataFrame) -> str:
    if 'price' in df.columns:
        return 'price'
    else:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            raise ValueError('В данных нет числовых колонок для расчета VaR.')
        else:
            return numeric_cols[0]


def historical(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, confidence_level=0.95, window=252) -> tuple[pd.DataFrame, float]:
    """\n    Расчет VaR историческим методом.\n\n    :param instrument: Инструмент.\n    :param calc_start: Начальная дата для расчета.\n    :param calc_end: Конечная дата для расчета.\n    :param confidence_level: Доверительный интервал (0.95, 0.99).\n    :param window: количество дней в истории.\n    :return: Pnl и значение VaR .\n    """
    pv = _get_pv_series(dataProvider, instrument, calc_start, calc_end, window + 1)
    returns = pv.to_frame('price')
    pnl = to_pnl(returns)
    if pnl.empty:
        raise ValueError('История доходностей пуста, невозможно рассчитать VaR.')
    data = pnl.tail(min(window, len(pnl)))
    horizon_days = max(1, (calc_end - calc_start).days)
    scaled_returns = data * np.sqrt(horizon_days)
    target_col = _resolve_target_column(scaled_returns)
    scaled_returns = scaled_returns.sort_values(by=target_col).reset_index(drop=True)
    alpha = 1 - confidence_level
    var = scaled_returns[target_col].quantile(alpha)
    return (scaled_returns, abs(float(var)))


def parametric(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, confidence_level=0.95, window=252) -> float:
    """\n    Параметрический VaR по формуле: -Mean + Std * Z-score\n    """
    pv = _get_pv_series(dataProvider, instrument, calc_start, calc_end, window + 1)
    returns = pv.to_frame('price')
    pnl = to_pnl(returns)
    if pnl.empty:
        raise ValueError('История доходностей пуста, невозможно рассчитать VaR.')
    data = pnl.tail(min(window, len(pnl)))
    target_col = _resolve_target_column(data)
    pnl_series = data[target_col]
    z_score = norm.ppf(confidence_level)
    var_1d = -pnl_series.mean() + pnl_series.std() * z_score
    horizon_days = max(1, (calc_end - calc_start).days)
    var_h = var_1d * np.sqrt(horizon_days)
    if np.isnan(var_h):
        raise ValueError('Получен NaN при расчете параметрического VaR. Проверьте входные данные.')
    return abs(float(var_h))




def historical_es(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, confidence_level: float = 0.95, window: int = 252) -> float:
    """
    ES историческим методом: среднее по хвосту PnL ниже VaR-отсечки.
    ES = |mean(PnL | PnL ≤ Q_α)|
    """
    pnl_series = _get_pnl_series(dataProvider, instrument, calc_start, calc_end, window)
    horizon_days = max(1, (calc_end - calc_start).days)
    pnl_scaled = pnl_series * np.sqrt(horizon_days)
    alpha = 1 - confidence_level
    var_cutoff = float(pnl_scaled.quantile(alpha))
    tail = pnl_scaled[pnl_scaled <= var_cutoff]
    if tail.empty:
        raise ValueError('Хвост PnL пуст — недостаточно данных для расчёта ES.')
    return abs(float(tail.mean()))


def parametric_es(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, confidence_level: float = 0.95, window: int = 252) -> float:
    """
    Параметрический ES(нормальное распределение):
    ES = (-μ + σ · φ(z_α) / α) · √horizon,
    где α = 1 - confidence_level, z_α = norm.ppf(α), φ — PDF нормального распределения.
    """
    pnl_series = _get_pnl_series(dataProvider, instrument, calc_start, calc_end, window)
    horizon_days = max(1, (calc_end - calc_start).days)
    alpha = 1 - confidence_level
    z_alpha = norm.ppf(alpha)
    es_1d = -pnl_series.mean() + pnl_series.std() * norm.pdf(z_alpha) / alpha
    es_h = float(es_1d) * np.sqrt(horizon_days)
    if np.isnan(es_h):
        raise ValueError('Получен NaN при расчёте параметрического ES. Проверьте входные данные.')
    return abs(float(es_h))


def _get_pv_series(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, window: int) -> pd.Series:
    """Возвращает сырой ряд PV (без преобразований), последние window точек."""
    return _get_pv_dispatch(dataProvider, instrument, calc_start, calc_end, window)


def _get_pnl_series(dataProvider: DataProvider, instrument: BaseInstrument, calc_start: datetime, calc_end: datetime, window: int) -> pd.Series:
    """Возвращает pct_change PnL-серию для одного инструмента (используется в ES и individual VaR)."""
    pv = _get_pv_series(dataProvider, instrument, calc_start, calc_end, window)
    pnl = pv.pct_change().dropna()
    if pnl.empty:
        raise ValueError(f'История доходностей пуста для {instrument.instrument_id}.')
    return pnl
