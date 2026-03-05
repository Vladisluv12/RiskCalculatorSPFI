from dataclasses import dataclass
from enum import Enum
from typing import Optional
from instruments.BaseInstrument import BaseInstrument
from instruments.BaseInstrument import Direction

class CurrencyPair(Enum):
    """Валютные пары из Приложения 2"""
    USD_RUB = "USD/RUB"
    EUR_RUB = "EUR/RUB"
    EUR_USD = "EUR/USD"
    CNY_RUB = "CNY/RUB"


@dataclass
class CurrencySwapContract(BaseInstrument):
    currency_pair: CurrencyPair # Валютная пара
    first_currency: str  # Первая валюта
    second_currency: str  # Вторая валюта
    
    fixed_sum_currency: str  # Валюта фиксированной суммы (может быть первой или второй валютой)
    fixed_sum: float  # Фиксированная сумма (номинал)
    spot_rate: float  # Курс спот (отношение второй валюты к единице первой)
    swap_points: int  # Своп-пункты (в пунктах, 1 пункт = 0.0001)
    additional_payment: Optional[float] = None  # Сумма дополнительного платежа
    additional_payment_direction: Optional[Direction] = None  # Получение/Уплата
    
    # Вычисляемые параметры
    initial_payment_first_currency: Optional[float] = None  # Сумма в первой валюте на near leg
    initial_payment_second_currency: Optional[float] = None  # Сумма во второй валюте на near leg
    final_payment_first_currency: Optional[float] = None  # Сумма в первой валюте на far leg
    final_payment_second_currency: Optional[float] = None  # Сумма во второй валюте на far leg
    
    def __post_init__(self):
        """Вычисление сумм платежей после инициализации"""
        self._calculate_payment_amounts()
    
    def _calculate_payment_amounts(self):
        """
        Расчет сумм платежей по п. 3.3 Спецификации
        
        (i) Валюта фиксированной суммы устанавливается в Предложении
        (ii) Фиксированная сумма - сумма в этой валюте
        (iii) Сумма в другой валюте определяется:
          А) Если фикс. валюта = первая: ФиксСумма * Курс спот
          Б) Если фикс. валюта = вторая: ФиксСумма / Курс спот
        """
        is_fixed_first = (self.fixed_sum_currency == self.first_currency)
        
        # Расчет первоначальных платежей (п. 3.3а)
        if is_fixed_first:
            self.initial_payment_first_currency = self.fixed_sum
            self.initial_payment_second_currency = self.fixed_sum * self.spot_rate
        else:
            self.initial_payment_second_currency = self.fixed_sum
            self.initial_payment_first_currency = self.fixed_sum / self.spot_rate
        
        # Форвардный курс = Спот + Своп-пункты (в абсолютном выражении)
        # Своп-пункты даны в пунктах, 1 пункт = 0.0001
        forward_rate = self.spot_rate + (self.swap_points * 0.0001)
        
        if is_fixed_first:
            self.final_payment_first_currency = self.fixed_sum
            self.final_payment_second_currency = self.fixed_sum * forward_rate
        else:
            self.final_payment_second_currency = self.fixed_sum
            self.final_payment_first_currency = self.fixed_sum / forward_rate

    def calculate_npv(self, current_spot_rate: float, current_swap_points: float) -> float:
        # Текущий форвард
        current_forward = current_spot_rate + (current_swap_points * 0.0001)
        
        # Исходный форвард
        original_forward = self.spot_rate + (self.swap_points * 0.0001)
        
        # Разница форвардов
        forward_diff = current_forward - original_forward
        
        if self.direction == Direction.SELL:
            # Sell
            mtm = -forward_diff * abs(self.final_payment_first_currency)
        else:
            # Buy
            mtm = forward_diff * abs(self.final_payment_first_currency)
        
        # Добавляем дополнительный платеж
        # if self.additional_payment:
        #     if self.additional_payment_direction == Direction.BUY:
        #         mtm += self.additional_payment
        #     else:
        #         mtm -= self.additional_payment
        
        return mtm
