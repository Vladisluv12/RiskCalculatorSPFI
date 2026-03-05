from datetime import date
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from instruments.BaseInstrument import BaseInstrument, Direction
from compute.curves.DiscountCurveFactory import DiscountCurveFactory

class SpotRateMethod(Enum):
    """Способы определения курса спот"""
    CBR = "CBR"  # Центральный Банк России
    MARKET = "Market"  # Рыночный курс

class CurrencyPair(Enum):
    USD_RUB = "USD/RUB"
    EUR_RUB = "EUR/RUB"
    EUR_USD = "EUR/USD"
    CNY_RUB = "CNY/RUB"


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
    spot_rate_method: Optional[SpotRateMethod] = None  # Способ определения курса спот
    spot_rate_date: Optional[date] = None
    working_days_offset: Optional[int] = None
    additional_payment: Optional[float] = None  # Сумма дополнительного платежа
    additional_payment_direction: Optional[Direction] = None  # Получение/Уплата

    def calculate_npv(
        self,
        spot_rate: float,
        rate_base: float,
        rate_quote: float,
        days_to_expiry: int,
        year_days: int = 365
    ) -> float:
        """
        Расчет недисконтированной справедливой стоимости (NPV) контракта.

        Args:
            spot_rate (float): Текущий рыночный курс спот S(t) (котировка: сколько котируемой валюты за единицу базовой).
            rate_base (float): Непрерывная безрисковая ставка для базовой валюты (в долях, напр. 0.05 для 5%).
            rate_quote (float): Непрерывная безрисковая ставка для котируемой/расчетной валюты (в долях).
            year_days (int): Количество дней в году (стандарт для валютного рынка — 365 или 360).

        Returns:
            float: Стоимость контракта (NPV) для держателя позиции.
                   Для позиции 'long' положительное значение означает прибыль при текущих условиях.
        """
        t = days_to_expiry / year_days

        forward_rate_fair = spot_rate * np.exp((rate_quote - rate_base) * t)

        if self.direction == Direction.BUY:
            # BUY
            rate_difference = forward_rate_fair - self.forward_rate
        else:  # SELL
            rate_difference = self.forward_rate - forward_rate_fair

        # Умножение на номинал
        mtm_value = self.notional * rate_difference
        
        # Добавляем дополнительный платеж
        # if self.additional_payment:
        #     if self.additional_payment_direction == Direction.BUY:
        #         mtm_value += self.additional_payment
        #     else:
        #         mtm_value -= self.additional_payment
        
        return round(mtm_value, 2)
    
