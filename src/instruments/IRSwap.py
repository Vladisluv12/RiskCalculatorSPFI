from dataclasses import dataclass
from instruments.BaseInstrument import BaseInstrument
from instruments.enums import Currency, DayCountConvention, FloatingIndex, OffsetRule, PaymentTiming


@dataclass
class InterestRateSwap(BaseInstrument):
    """Процентный своп (IRS/OIS)"""
    currency: Currency
    
    # Фиксированная нога
    fixed_rate: float # в процентах
    fixed_day_count: DayCountConvention
    fixed_payment_timing: PaymentTiming
    fixed_offset_rule: OffsetRule
    
    # Плавающая нога
    floating_index: FloatingIndex
    floating_spread: float # в bp
    floating_day_count: DayCountConvention
    floating_payment_timing: PaymentTiming
    floating_offset_rule: OffsetRule
    