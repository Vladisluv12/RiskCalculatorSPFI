from dataclasses import dataclass
from typing import Optional
from instruments.BaseInstrument import BaseInstrument
from instruments.enums import CurrencyPair


@dataclass
class CurrencySwapContract(BaseInstrument):
    currency_pair: CurrencyPair # Валютная пара
    base_currency: str  # Базовая валюта
    quote_currency: str  # Расчетная валюта

    fixed_sum_currency: str  # Валюта фиксированной суммы (ожидается базовая валюта)
    fixed_sum: float  # Фиксированная сумма в fixed_sum_currency
    spot_rate: float  # Зафиксированный в сделке спот на near leg
    swap_points: int  # Своп-пункты (в пунктах, 1 пункт = 0.0001)
    reverse_rate: Optional[float] = None  # K: зафиксированный курс обратного обмена (far leg)
    # additional_payment: Optional[float] = None  # Сумма дополнительного платежа
    # additional_payment_direction: Optional[Direction] = None  # Получение/Уплата
    
    # Вычисляемые параметры
    initial_payment_first_currency: Optional[float] = None  # Сумма в первой валюте на near leg
    initial_payment_second_currency: Optional[float] = None  # Сумма во второй валюте на near leg
    final_payment_first_currency: Optional[float] = None  # Сумма в первой валюте на far leg
    final_payment_second_currency: Optional[float] = None  # Сумма во второй валюте на far leg

    @property
    def forward_rate(self) -> float:
        """Курс K для far leg: явно заданный или spot + swap_points."""
        if self.reverse_rate is not None:
            return float(self.reverse_rate)
        return float(self.spot_rate + self.swap_points * 0.0001)
