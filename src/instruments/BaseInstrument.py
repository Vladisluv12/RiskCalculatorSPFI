from datetime import datetime
from dataclasses import dataclass
from instruments.enums import Direction


@dataclass
class BaseInstrument:
    instrument_id: str
    notional: float
    direction: Direction
    start_date: datetime
    end_date: datetime