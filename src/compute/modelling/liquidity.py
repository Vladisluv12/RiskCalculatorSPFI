import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from instruments.enums import Direction


@dataclass
class LiquidityParams:
    k: float = 3.0                        # калибровочный коэффициент (российский рынок)
    floor_spread: float = 0.001           # минимальный спред (10 bps)
    alpha: float = 0.10                   # асимметрия BUY/SELL
    lambda_: float = 0.94                 # EWMA decay
    avg_daily_volume: dict = field(default_factory=dict)  # {currency_pair: float}
    observed_spreads: dict = field(default_factory=dict)  # {currency_pair: spread_pct}


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
    instrument_id: str = "",
) -> pd.Series:
    """
    Эмулированная серия s%_adj(t) за исторический период.

    s%(t)      = max(k × σ_ewma(t) × √tenor_years, floor_spread)
    dir_adj    = (1 + α) если BUY, (1 − α) если SELL
    size_adj   = 1 + 0.5 × (notional / ADV)  если ADV задан, иначе 1.0
    s%_adj(t)  = s%(t) × dir_adj × size_adj
    """
    if instrument_id in params.observed_spreads:
        val = params.observed_spreads[instrument_id]
        if isinstance(val, pd.Series):
            combined = val.reindex(val.index.union(fx_returns.index)).sort_index().ffill().bfill()
            return combined.reindex(fx_returns.index).fillna(params.floor_spread)
        return pd.Series(float(val), index=fx_returns.index)
    sigma_ewma = estimate_ewma_vol(fx_returns, params.lambda_)
    base_spread = np.maximum(
        params.k * sigma_ewma * np.sqrt(max(tenor_years, 1 / 365)),
        params.floor_spread,
    )
    dir_adj = (1.0 + params.alpha) if direction == Direction.BUY else (1.0 - params.alpha)
    adv = params.avg_daily_volume.get(currency_pair)
    size_adj = 1.0 + 0.5 * (notional / adv) if adv else 1.0
    return base_spread * dir_adj * size_adj


def compute_lc(
    mid_pv: float,
    spread_series: pd.Series,
    z_alpha: float,
) -> dict:
    """
    LC_normal   = 0.5 × |mid_pv| × s%_last
    LC_stressed = 0.5 × |mid_pv| × (s%_last + z_alpha × σ_spread)

    Возвращает {'normal': float, 'stressed': float}.
    """
    s_last = float(spread_series.iloc[-1])
    sigma_spread = float(spread_series.std()) if len(spread_series) > 1 else 0.0
    abs_pv = abs(mid_pv)
    lc_normal = 0.5 * abs_pv * s_last
    lc_stressed = 0.5 * abs_pv * (s_last + z_alpha * sigma_spread)
    return {'normal': lc_normal, 'stressed': lc_stressed}
