from datetime import datetime
import pandas as pd

from instruments.BaseInstrument import BaseInstrument
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap
from utils.DataProvider import DataProvider
from compute.pricers.ForwardPricer import ForwardPricer
from compute.pricers.CurrencySwapPricer import CurrencySwapPricer


def get_pv_series(
    dataProvider: DataProvider,
    instrument: BaseInstrument,
    calc_start: datetime,
    calc_end: datetime,
    window: int,
) -> pd.Series:
    if isinstance(instrument, CurrencyForwardContract):
        returns = ForwardPricer(365).calculate_pv(instrument, dataProvider, calc_start, calc_end)
    elif isinstance(instrument, CurrencySwapContract):
        returns = CurrencySwapPricer(365).calculate_pv(instrument, dataProvider, calc_start, calc_end)
    elif isinstance(instrument, InterestRateSwap):
        from compute.pricers.IRSPricer import IRSPricer  # deferred to avoid circular import at module load
        returns = IRSPricer(365).calculate_pv(instrument, dataProvider, calc_start, calc_end)
    else:
        raise ValueError(f'Неизвестный тип инструмента: {type(instrument).__name__}')
    if returns.empty:
        raise ValueError(f'Не удалось получить историю PV для {instrument.instrument_id}.')
    return returns['price'].tail(min(window, len(returns))).rename(instrument.instrument_id)
