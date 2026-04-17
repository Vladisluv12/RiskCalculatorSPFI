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


def estimate_spread_series(
    fx_returns: pd.Series,
    tenor_years: float,
    direction: Direction,
    notional: float,
    currency_pair: str,
    params: LiquidityParams,
) -> pd.Series:
    """
    Эмулированная серия s%_adj(t) за исторический период.

    s%(t)      = max(k × σ_ewma(t) × √tenor_years, floor_spread)
    dir_adj    = (1 + α) если BUY, (1 − α) если SELL
    size_adj   = 1 + 0.5 × (notional / ADV)  если ADV задан, иначе 1.0
    s%_adj(t)  = s%(t) × dir_adj × size_adj
    """
    sigma_ewma = estimate_ewma_vol(fx_returns, params.lambda_)
    base_spread = np.maximum(
        params.k * sigma_ewma * np.sqrt(max(tenor_years, 1 / 365)),
        params.floor_spread,
    )
    dir_adj = (1.0 + params.alpha) if direction == Direction.BUY else (1.0 - params.alpha)
    adv = params.avg_daily_volume.get(currency_pair)
    size_adj = 1.0 + 0.5 * (notional / adv) if adv else 1.0
    return base_spread * dir_adj * size_adj
