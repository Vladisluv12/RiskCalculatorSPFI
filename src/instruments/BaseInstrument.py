from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class Direction(Enum):
    BUY = "Buy"
    SELL = "Sell"

@dataclass
class BaseInstrument:
    instrument_id: str
    notional: float
    direction: Direction 
    start_date: datetime
    end_date: datetime
