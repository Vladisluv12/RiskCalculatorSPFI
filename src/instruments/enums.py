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

class DayCountConvention(Enum):
    """Конвенция для подсчёта дней в процентах"""
    _30E_360 = '30E/360'
    ACT_360 = 'ACT/360'
    ACT_365 = 'ACT/365'
    ACT_ACT = 'ACT/ACT (ISDA)'

class PaymentTiming(Enum):
    """Частота выплат"""
    MONTHLY = 'Ежемесячно'
    QUARTERLY = 'Ежеквартально'
    SEMI_ANNUALLY = 'Каждые полгода'
    ANNUALLY = 'Ежегодно'
    END_OF_PERIOD = 'В конце периода'

class OffsetRule(Enum):
    """Правило смещения дат выплат"""
    NONE = 'Не применять'
    ONE_DAY = '+1 рабочий день'
    TWO_DAYS = '+2 рабочих дня'
    
class Currency(Enum):
    USD = 'USD'
    RUB = 'RUB'
    EUR = 'EUR'
    CNY = 'CNY'
    
from enum import Enum

class FloatingIndex(Enum):
    """Плавающие индексы и ставки для процентных свопов (IRS/OIS)"""
    RUONIA_AVG = "RUONIA Avg."
    RUONIA_COMP = "RUONIA Comp."
    ESTR_COMP = "ESTR Comp."
    SOFR_COMP = "SOFR Comp."
    OIS_FX = "OIS FX"
    EURIBOR_EUR_1M = "Euribor EUR 1m"
    EURIBOR_EUR_3M = "Euribor EUR 3m"
    EURIBOR_EUR_6M = "Euribor EUR 6m"
    RUSFAR_RUB_3M = "RUSFAR RUB 3m"
    RUSFAR_RUB_ON = "RusFar RUB O/N"
    RUSFARCNY_COMP = "RUSFARCNY Comp."
    RUB_KEY_RATE = "RUB KeyRate"
