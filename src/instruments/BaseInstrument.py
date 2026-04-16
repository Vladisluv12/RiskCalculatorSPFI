from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class Direction(Enum):
    BUY = 'Buy'
    SELL = 'Sell'

class CurrencyPair(Enum):
    """Валютные пары из Приложения 2"""
    USD_RUB = 'USD/RUB'
    EUR_RUB = 'EUR/RUB'
    EUR_USD = 'EUR/USD'
    CNY_RUB = 'CNY/RUB'

@dataclass
class BaseInstrument:
    instrument_id: str
    notional: float
    direction: Direction
    start_date: datetime
    end_date: datetime