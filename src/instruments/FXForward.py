from typing import Optional
from dataclasses import dataclass
from instruments.BaseInstrument import BaseInstrument
from instruments.enums import CurrencyPair

@dataclass
class CurrencyForwardContract(BaseInstrument):
    # основные параметры
    currency_pair: CurrencyPair
    base_currency: str  # Базовая валюта
    quote_currency: str  # Расчетная валюта (для расчетного) / Вторая валюта (для поставочного)
    forward_rate: float
    spot_rate: Optional[float] = None
    is_ndf: bool = False
    # Методы определения курсов (если ndf)
    # spot_rate_method: Optional[SpotRateMethod] = None  # Способ определения курса спот
    # spot_rate_date: Optional[date] = None
    # working_days_offset: Optional[int] = None