import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from instruments.BaseInstrument import Direction


@dataclass
class LiquidityParams:
    k: float = 3.0                        # калибровочный коэффициент (российский рынок)
    floor_spread: float = 0.001           # минимальный спред (10 bps)
    alpha: float = 0.10                   # асимметрия BUY/SELL
    lambda_: float = 0.94                 # EWMA decay (RiskMetrics)
    avg_daily_volume: dict = field(default_factory=dict)  # {currency_pair: float}


def estimate_ewma_vol(fx_returns: pd.Series, lambda_: float = 0.94) -> pd.Series:
    """
    EWMA-волатильность дневных доходностей FX.
    σ²(t) = λ·σ²(t-1) + (1-λ)·r²(t)
    Возвращает серию σ(t) (std, не дисперсия).
    """
    variance = fx_returns.pow(2).ewm(alpha=1.0 - lambda_, adjust=False).mean()
    return np.sqrt(variance)
