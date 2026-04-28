# https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/shared/pdf/technical_notes.pdf - eur
# https://www.moex.com/ru/documents/14299 - rub
# https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/more?locale=en_US - cny
# https://fred.stlouisfed.org/series/FF - usd

# TODO: пофиксить данные по кривой для юаня, в 2017 году была добавлена ключевая ставка, которая чёто совсем не соотносится с данными там


import pandas as pd
import numpy as np
from scipy.interpolate import interp1d


def get_risk_free_rate(currency: str, target_tenor, curve_data: pd.DataFrame) -> pd.DataFrame:
    """
    Получение безрисковой ставки для указанной валюты.

    Parameters:
    -----------
    currency : str
        Код валюты ('USD', 'EUR', 'RUB', 'CNY')
    target_tenor : float | pd.Series
        Целевой срок (в годах). Может быть скаляром или Series (индекс = даты),
        чтобы использовать скользящий тенор для каждой даты оценки.
    curve_data : pd.DataFrame
        DataFrame с параметрами кривой (индекс = даты).

    Returns:
    --------
    pd.DataFrame с колонками ['tenor', 'rf_rate'], индекс = даты из curve_data.
    """
    is_series_tenor = isinstance(target_tenor, pd.Series)

    if currency.upper() == 'USD':
        tenor_cols = [col for col in curve_data.columns if col != 'date']
        x_tenors = np.array([float(col.replace('y', '')) for col in tenor_cols])
        results = []
        for _, row in curve_data.iterrows():
            date = row.name
            tenor = float(target_tenor.at[date]) if is_series_tenor else target_tenor  # type: ignore[arg-type]
            y_rates = np.array(row[tenor_cols].values, dtype=float) / 100
            f_interp = interp1d(x_tenors, y_rates, kind='linear', fill_value='extrapolate')  # type: ignore[call-overload]
            rate = float(f_interp(tenor))
            results.append({'date': date, 'tenor': tenor, 'rf_rate': rate})
        res_df = pd.DataFrame(results)
        return res_df.set_index('date')

    elif currency.upper() == 'RUB':
        k = 1.6
        a = np.zeros(10)
        b = np.zeros(10)
        a[1] = 0
        a[2] = 0.6
        for i in range(2, 9):
            a[i + 1] = a[i] + a[2] * k ** (i - 1)
        b[1] = a[2]
        for i in range(1, 9):
            b[i + 1] = b[i] * k

        row = curve_data
        beta0 = row['B1']
        beta1 = row['B2']
        beta2 = row['B3']
        tau = row['T1']
        g = [row[f'G{i}'] for i in range(1, 10)]

        t = target_tenor

        term1 = (beta1 + beta2) * (tau / t) * (1 - np.exp(-t / tau))
        term2 = -beta2 * np.exp(-t / tau)
        base_rate = beta0 + term1 + term2

        correction = 0
        for i in range(1, 10):
            idx = i - 1
            exponent = -(t - a[i]) ** 2 / b[i] ** 2
            correction += g[idx] * np.exp(exponent)

        rf_rate = (base_rate + correction) / 10000
        result = pd.DataFrame({
            'date': curve_data.index,
            'tenor': t if is_series_tenor else pd.Series([t] * len(curve_data), index=curve_data.index),
            'rf_rate': rf_rate,
        })
        result.set_index('date', inplace=True)
        return result

    elif currency.upper() == 'EUR':
        b0 = curve_data['BETA0']
        b1 = curve_data['BETA1']
        b2 = curve_data['BETA2']
        b3 = curve_data['BETA3']
        tau1 = curve_data['TAU1']
        tau2 = curve_data['TAU2']

        t = target_tenor  # scalar or Series aligned with curve_data

        if not is_series_tenor and t <= 0:
            rf_rates = b0 + b1
        else:
            exp1 = np.exp(-t / tau1)
            term1 = b1 * ((1 - exp1) / (t / tau1))
            term2 = b2 * ((1 - exp1) / (t / tau1) - exp1)
            exp2 = np.exp(-t / tau2)
            term3 = b3 * ((1 - exp2) / (t / tau2) - exp2)
            rf_rates = b0 + term1 + term2 + term3

        result = pd.DataFrame({
            'date': curve_data.index,
            'tenor': t if is_series_tenor else pd.Series([t] * len(curve_data), index=curve_data.index),
            'rf_rate': rf_rates / 100,
        })
        return result.set_index('date')

    elif currency.upper() == 'CNY':
        tenor_map = {
            '0d': 0.0, '1m': 1/12, '2m': 2/12, '3m': 0.25, '6m': 0.5,
            '9m': 0.75, '1y': 1.0, '2y': 2.0, '3y': 3.0, '4y': 4.0,
            '5y': 5.0, '6y': 6.0, '7y': 7.0, '8y': 8.0, '9y': 9.0, '10y': 10.0,
        }
        available_cols = [c for c in curve_data.columns if c in tenor_map]
        x_points = [tenor_map[c] for c in available_cols]
        results = []
        for _, row in curve_data.iterrows():
            date = row.name
            tenor = float(target_tenor.at[date]) if is_series_tenor else target_tenor  # type: ignore[arg-type]
            y_rates = np.array(row[available_cols].values, dtype=float) / 100
            f_interp = interp1d(x_points, y_rates, kind='linear', fill_value='extrapolate')  # type: ignore[call-overload]
            rate = float(f_interp(tenor))
            results.append({'date': date, 'tenor': tenor, 'rf_rate': rate})
        res_df = pd.DataFrame(results)
        return res_df.set_index('date')

    else:
        raise ValueError(f'Валюта {currency} не поддерживается.')


_OIS_TENOR_YEARS: dict[str, float] = {
    "1w": 7 / 365,
    "1m": 30 / 365,
    "3m": 90 / 365,
    "6m": 180 / 365,
    "1y": 1.0,
    "2y": 2.0,
    "3y": 3.0,
    "5y": 5.0,
    "7y": 7.0,
    "10y": 10.0,
}


def get_ois_rate(
    tenor_series: pd.Series,
    ois_curve: pd.DataFrame,
) -> pd.Series:
    """
    Interpolate OIS spot rate for each (date, tenor) pair.

    Parameters
    ----------
    tenor_series : pd.Series
        Index = dates, values = tenor in years (e.g. 0.5 for 6m).
    ois_curve : pd.DataFrame
        Index = dates, columns = ["1w","1m",...,"10y"], values = % per annum.
        Need not cover every date — nearest prior date is used (ffill).

    Returns
    -------
    pd.Series
        OIS rate as fraction (e.g. 0.16 for 16%), same index as tenor_series.
        NaN where OIS data is entirely unavailable for a date.
    """
    # Sort columns by tenor so interp1d receives monotonically increasing x
    col_order = sorted(ois_curve.columns, key=lambda c: _OIS_TENOR_YEARS[c])
    ois_curve = ois_curve[col_order]
    x_knots = np.array([_OIS_TENOR_YEARS[c] for c in col_order])
    ois_index = ois_curve.index
    results = []

    for date in tenor_series.index:
        tenor = float(tenor_series.at[date])

        # Find nearest available OIS date (forward-fill)
        available = ois_index[ois_index <= date]
        if len(available) == 0:
            results.append(np.nan)
            continue
        row = ois_curve.loc[available[-1]]

        y_rates = row.values.astype(float)
        valid = ~np.isnan(y_rates)
        if valid.sum() < 2:
            results.append(np.nan)
            continue

        # Clip tenor to range of available (non-NaN) knots for this row
        tenor = max(tenor, x_knots[valid][0])

        rate_pct = float(interp1d(
            x_knots[valid], y_rates[valid],
            kind='linear', fill_value='extrapolate',
        )(tenor))
        results.append(rate_pct / 100.0)  # % → fraction

    return pd.Series(results, index=tenor_series.index, name='ois_rate')
