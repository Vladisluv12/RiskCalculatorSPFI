import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
from compute.pricers.CurrencySwapPricer import CurrencySwapPricer
from compute.pricers.ForwardPricer import ForwardPricer
from instruments.BaseInstrument import BaseInstrument
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from utils.DataProvider import DataProvider


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
    returns = pd.DataFrame()
    if isinstance(instrument, CurrencyForwardContract):
        fxPricer = ForwardPricer(365)
        returns = fxPricer.calculate_pv(instrument, dataProvider, calc_start, calc_end)
    else:
        if isinstance(instrument, CurrencySwapContract):
            swapPricer = CurrencySwapPricer(365)
            returns = swapPricer.calculate_pv(instrument, dataProvider, calc_start, calc_end)
    if returns.empty:
        raise ValueError('Не удалось получить историю PV для расчета исторического VaR.')
    else:
        pnl = to_pnl(returns)
        if pnl.empty:
            raise ValueError('История доходностей пуста, невозможно рассчитать VaR.')
        else:
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
    returns = pd.DataFrame()
    if isinstance(instrument, CurrencyForwardContract):
        fxPricer = ForwardPricer(365)
        returns = fxPricer.calculate_pv(instrument, dataProvider, calc_start, calc_end)
    else:
        if isinstance(instrument, CurrencySwapContract):
            swapPricer = CurrencySwapPricer(365)
            returns = swapPricer.calculate_pv(instrument, dataProvider, calc_start, calc_end)
    if returns.empty:
        raise ValueError('Не удалось получить историю PV для расчета параметрического VaR.')
    else:
        pnl = to_pnl(returns)
        if pnl.empty:
            raise ValueError('История доходностей пуста, невозможно рассчитать VaR.')
        else:
            data = pnl.tail(min(window, len(pnl)))
            target_col = _resolve_target_column(data)
            pnl_series = data[target_col]
            z_score = norm.ppf(confidence_level)
            var_1d = -pnl_series.mean() + pnl_series.std() * z_score
            horizon_days = max(1, (calc_end - calc_start).days)
            var_h = var_1d * np.sqrt(horizon_days)
            if np.isnan(var_h):
                raise ValueError('Получен NaN при расчете параметрического VaR. Проверьте входные данные.')
            else:
                return abs(float(var_h))


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


def portfolio_historical_es(dataProvider: DataProvider, instruments: list, calc_start: datetime, calc_end: datetime, confidence_level: float = 0.95, window: int = 252, horizon: int = 1) -> float:
    """
    Исторический ES для портфеля: ES по агрегированному PnL (сумма позиций).
    """
    series_list = [_get_pnl_series(dataProvider, inst, calc_start, calc_end, window) for inst in instruments]
    pnl_matrix = _deduplicate_columns(pd.concat(series_list, axis=1).dropna())
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
    pnl_matrix = _deduplicate_columns(pd.concat(series_list, axis=1).dropna())
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
    pv_matrix = _deduplicate_columns(pd.concat(pv_list, axis=1).dropna())
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
    pv_matrix = _deduplicate_columns(pd.concat(pv_list, axis=1).dropna())
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


def portfolio_lvar(
    var_portfolio: float,
    instruments: list,
    dataProvider: DataProvider,
    calc_start: datetime,
    calc_end: datetime,
    params,                        # LiquidityParams
    T: int = 1,
    confidence_level: float = 0.95,
    window: int = 252,
) -> dict:
    """
    LVaR для портфеля.

    Возвращает:
      instrument_lc  — dict {id: {'normal': float, 'stressed': float}}
      lc_total       — {'normal': float, 'stressed': float}
      lvar_normal    — float: (VaR + LC_normal) / t_factor
      lvar_stressed  — float: (VaR + LC_stressed) / t_factor
      t_factor       — float: √((1+T)(1+2T)/(6T))
    """
    from compute.risk.liquidity import estimate_spread_series, compute_lc
    from scipy.stats import norm

    z_alpha = float(norm.ppf(confidence_level))
    t_factor = float(np.sqrt((1 + T) * (1 + 2 * T) / (6 * T)))

    instrument_lc: dict = {}

    for inst in instruments:
        pair_ticker = inst.currency_pair.value.replace('/', '')  # 'USDRUB'
        pair_label = inst.currency_pair.value                    # 'USD/RUB'

        try:
            currency_df = dataProvider.get_currency_data(pair_ticker, calc_start, calc_end)
        except Exception:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        if currency_df.empty:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        fx_returns = currency_df['curs'].pct_change().dropna().tail(window)

        calc_end_ts = pd.Timestamp(calc_end)
        end_dt_ts = pd.Timestamp(inst.end_date)
        tenor_years = max(1 / 365, (end_dt_ts - calc_end_ts).days / 365)

        try:
            pv_series = _get_pv_series(dataProvider, inst, calc_start, calc_end, window)
            mid_pv = float(pv_series.iloc[-1])
        except Exception:
            instrument_lc[inst.instrument_id] = {'normal': 0.0, 'stressed': 0.0}
            continue

        spread_series = estimate_spread_series(
            fx_returns=fx_returns,
            tenor_years=tenor_years,
            direction=inst.direction,
            notional=float(inst.notional),
            currency_pair=pair_label,
            params=params,
        )

        lc = compute_lc(mid_pv=mid_pv, spread_series=spread_series, z_alpha=z_alpha)
        instrument_lc[inst.instrument_id] = lc

    lc_total_normal = sum(v['normal'] for v in instrument_lc.values())
    lc_total_stressed = sum(v['stressed'] for v in instrument_lc.values())

    return {
        'instrument_lc': instrument_lc,
        'lc_total': {'normal': lc_total_normal, 'stressed': lc_total_stressed},
        'lvar_normal': (var_portfolio + lc_total_normal) / t_factor,
        'lvar_stressed': (var_portfolio + lc_total_stressed) / t_factor,
        't_factor': t_factor,
    }
