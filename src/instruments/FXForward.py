from datetime import date
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from instruments.BaseInstrument import BaseInstrument

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

    # def calculate_settlement_amount(self, spot_rate: float) -> float:
    #     """
    #     Расчет суммы платежа для расчетного договора
    #
    #     Args:
    #         spot_rate: Курс спот на дату оценки
    #
    #     Returns:
    #         Сумма платежа в валюте суммы платежа
    #     """
    #     if self.settlement_currency == self.base_currency:
    #         # Формула: Номинальная сумма × [1 - Форвардный курс / Курс спот]
    #         amount = self.nominal_amount_base * (1 - self.forward_rate / spot_rate)
    #     elif self.settlement_currency == self.quote_currency:
    #         # Формула: Номинальная сумма × [Курс спот - Форвардный курс]
    #         amount = self.nominal_amount_base * (spot_rate - self.forward_rate)
    #     else:
    #         raise ValueError(f"Неизвестная валюта суммы платежа: {self.settlement_currency}")
    #
    #     # Округление согласно п. 4.1(a)
    #     return round(amount, 2)

    # НУЖЕН метод для определения платежа (NPV)

    # ВЫНЕСТИ ЭТОТ МЕТОД В ВАЛИДАТОР
    # def is_valid_nominal_amount(self) -> bool:
    #     """
    #     Проверка минимального значения номинальной суммы
    #     согласно Приложению 2
    #     """
    #     min_amounts = {
    #         CurrencyPair.USD_RUB: 1000,  # 1000 USD
    #         CurrencyPair.EUR_RUB: 1000,  # 1000 EUR
    #         CurrencyPair.EUR_USD: 1000,  # 1000 EUR
    #         CurrencyPair.CNY_RUB: 1000,  # 1000 CNY
    #     }
    #
    #     min_amount = min_amounts.get(self.currency_pair)
    #     if min_amount is None:
    #         return True
    #
    #     return self.nominal_amount_base >= min_amount