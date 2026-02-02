import pandas as pd
import numpy as np
from scipy.stats import norm
import utils.data_manager as data_manager


def to_pnl(returns):
    """
    Преобразует цены в доходности (PnL).
    """
    return returns.pct_change().dropna()

def historical(ticker, horizon=1, confidence_level=0.95, window=252) -> tuple[pd.DataFrame, float]:
    """
    Расчет VaR историческим методом.

    :param ticker: Тикер инструмента.
    :param horizon: Временной горизонт в днях.
    :param confidence_level: Доверительный интервал (0.95, 0.99).
    :param window: количество дней в истории.
    :return: Pnl и значение VaR .
    """
    returns = data_manager.get_data(ticker="USDRUB", ctype="currency", days=window)
    pnl = to_pnl(returns)
    if len(pnl) < window:
        data = pnl.tail(window)
    else:
        raise ValueError("Недостаточно данных для выбранного окна.")

    scaled_returns = data * np.sqrt(horizon)
    scaled_returns = scaled_returns.sort_values(by='curs').reset_index(drop=True)
    alpha = 1 - confidence_level
    var = scaled_returns.quantile(alpha)

    return scaled_returns, var.abs().iloc[0]


def parametric(ticker, horizon=1, confidence_level=0.95, window=252) -> float:
    """
    Параметрический VaR по формуле: -Mean + Std * Z-score
    """
    returns = data_manager.get_data(ticker="USDRUB", ctype="currency", days=window)
    pnl = to_pnl(returns)
    z_score = norm.ppf(confidence_level)
    var_1d = -pnl.mean() + pnl.std() * z_score
    var_h = var_1d * np.sqrt(horizon)
    return var_h.abs().iloc[0]