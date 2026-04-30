"""
Генерация демонстрационных портфелей для курсовой работы.

Создаёт 4 портфеля с различным составом и уровнем корреляции:

  1. pure_irs_rub         — только RUB IRS/OIS (высокая корреляция)
  2. irs_dominated_rub    — RUB IRS + FX USD/RUB (высокая-средняя)
  3. balanced_multiccy    — IRS в RUB + EUR + FX (средняя)
  4. fx_diversified       — только FX по 4 парам (низкая корреляция)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime

from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap
from instruments.enums import (
    Currency, CurrencyPair, DayCountConvention, Direction,
    FloatingIndex, OffsetRule, PaymentTiming,
)
from iolib.portfolio_io import PortfolioExporter
from iolib.serializers.json_serializer import JsonSerializer

# ---------------------------------------------------------------------------
# Опорные даты
# ---------------------------------------------------------------------------
TODAY      = datetime(2025, 4, 11)
T2         = datetime(2025, 4, 15)   # T+2 — стандартный старт свопов
END_1Y     = datetime(2026, 4, 15)
END_2Y     = datetime(2027, 4, 15)
END_3Y     = datetime(2028, 4, 15)
FWD_1M     = datetime(2025, 5, 15)
FWD_3M     = datetime(2025, 7, 15)
FWD_6M     = datetime(2025, 10, 15)
SWAP_3M    = datetime(2025, 7, 15)

# ---------------------------------------------------------------------------
# Строительные блоки
# ---------------------------------------------------------------------------

def rub_irs(inst_id, tenor_end, fixed_rate, timing=PaymentTiming.QUARTERLY,
            floating_index=FloatingIndex.RUONIA_COMP, notional=1_000_000.0,
            direction=Direction.BUY):
    return InterestRateSwap(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=T2,
        end_date=tenor_end,
        currency=Currency.RUB,
        fixed_rate=fixed_rate,
        fixed_day_count=DayCountConvention.ACT_365,
        fixed_payment_timing=timing,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=floating_index,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_365,
        floating_payment_timing=timing,
        floating_offset_rule=OffsetRule.NONE,
    )


def eur_irs(inst_id, tenor_end, fixed_rate, timing=PaymentTiming.SEMI_ANNUALLY,
            notional=500_000.0, direction=Direction.BUY):
    return InterestRateSwap(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=T2,
        end_date=tenor_end,
        currency=Currency.EUR,
        fixed_rate=fixed_rate,
        fixed_day_count=DayCountConvention.ACT_360,
        fixed_payment_timing=timing,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=FloatingIndex.EURIBOR_EUR_6M,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_360,
        floating_payment_timing=timing,
        floating_offset_rule=OffsetRule.NONE,
    )


def usdrub_fwd(inst_id, end_date, rate, notional=500_000.0, direction=Direction.BUY):
    return CurrencyForwardContract(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=TODAY,
        end_date=end_date,
        currency_pair=CurrencyPair.USD_RUB,
        base_currency='USD',
        quote_currency='RUB',
        forward_rate=rate,
        spot_rate=None,
        is_ndf=True,
    )


def eurrub_fwd(inst_id, end_date, rate, notional=500_000.0, direction=Direction.BUY):
    return CurrencyForwardContract(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=TODAY,
        end_date=end_date,
        currency_pair=CurrencyPair.EUR_RUB,
        base_currency='EUR',
        quote_currency='RUB',
        forward_rate=rate,
        spot_rate=None,
        is_ndf=False,
    )


def cnyrub_fwd(inst_id, end_date, rate, notional=2_000_000.0, direction=Direction.BUY):
    return CurrencyForwardContract(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=TODAY,
        end_date=end_date,
        currency_pair=CurrencyPair.CNY_RUB,
        base_currency='CNY',
        quote_currency='RUB',
        forward_rate=rate,
        spot_rate=None,
        is_ndf=False,
    )


def eurusd_fwd(inst_id, end_date, rate, notional=300_000.0, direction=Direction.SELL):
    return CurrencyForwardContract(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=TODAY,
        end_date=end_date,
        currency_pair=CurrencyPair.EUR_USD,
        base_currency='EUR',
        quote_currency='USD',
        forward_rate=rate,
        spot_rate=None,
        is_ndf=False,
    )


def usdrub_swap(inst_id, notional=500_000.0, direction=Direction.BUY):
    return CurrencySwapContract(
        instrument_id=inst_id,
        notional=notional,
        direction=direction,
        start_date=T2,
        end_date=SWAP_3M,
        currency_pair=CurrencyPair.USD_RUB,
        base_currency='USD',
        quote_currency='RUB',
        fixed_sum_currency='USD',
        fixed_sum=notional,
        spot_rate=85.50,
        swap_points=350,
        reverse_rate=85.535,
    )


# ---------------------------------------------------------------------------
# Портфели
# ---------------------------------------------------------------------------

PORTFOLIOS = {
    # -----------------------------------------------------------------------
    # 1. Только рублёвые процентные свопы (RUONIA OIS + KeyRate IRS)
    #    Инструменты: 5 IRS, 100% IRS
    #    Ожидаемая корреляция: высокая — все завязаны на рублёвую кривую
    # -----------------------------------------------------------------------
    "pure_irs_rub": [
        rub_irs("RUB OIS RUONIA 1Y",     END_1Y, fixed_rate=0.1650,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB OIS RUONIA 2Y",     END_2Y, fixed_rate=0.1680,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB OIS RUONIA 3Y",     END_3Y, fixed_rate=0.1710,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB IRS KEYRATE 1Y",    END_1Y, fixed_rate=0.2050,
                floating_index=FloatingIndex.RUB_KEY_RATE,
                timing=PaymentTiming.SEMI_ANNUALLY, direction=Direction.SELL),
        rub_irs("RUB IRS KEYRATE 2Y",    END_2Y, fixed_rate=0.1920,
                floating_index=FloatingIndex.RUB_KEY_RATE,
                timing=PaymentTiming.SEMI_ANNUALLY),
    ],

    # -----------------------------------------------------------------------
    # 2. Рублёвые IRS + FX USD/RUB (всё в одном рублёвом сегменте)
    #    Инструменты: 3 IRS + 2 FX, 60% IRS
    #    Ожидаемая корреляция: высокая — RUB-курс и RUB-ставки коррелируют
    # -----------------------------------------------------------------------
    "irs_dominated_rub": [
        rub_irs("RUB OIS RUONIA 1Y",  END_1Y, fixed_rate=0.1650,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB OIS RUONIA 2Y",  END_2Y, fixed_rate=0.1680,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB IRS KEYRATE 1Y", END_1Y, fixed_rate=0.2050,
                floating_index=FloatingIndex.RUB_KEY_RATE,
                timing=PaymentTiming.SEMI_ANNUALLY),
        usdrub_fwd("FWD USDRUB 1M", FWD_1M, rate=87.20),
        usdrub_fwd("FWD USDRUB 3M", FWD_3M, rate=88.80, direction=Direction.SELL),
    ],

    # -----------------------------------------------------------------------
    # 3. Смешанный мультивалютный (IRS в RUB + EUR + FX разные пары)
    #    Инструменты: 2 RUB IRS + 1 EUR IRS + 2 FX, 60% IRS
    #    Ожидаемая корреляция: средняя — EUR и RUB кривые частично независимы
    # -----------------------------------------------------------------------
    "balanced_multiccy": [
        rub_irs("RUB OIS RUONIA 1Y",   END_1Y, fixed_rate=0.1650,
                floating_index=FloatingIndex.RUONIA_COMP),
        rub_irs("RUB IRS KEYRATE 2Y",  END_2Y, fixed_rate=0.1920,
                floating_index=FloatingIndex.RUB_KEY_RATE,
                timing=PaymentTiming.SEMI_ANNUALLY),
        eur_irs("EUR IRS EURIBOR6M 2Y", END_2Y, fixed_rate=0.0340),
        eurrub_fwd("FWD EURRUB 3M",    FWD_3M, rate=95.40),
        usdrub_swap("SWAP USDRUB 3M"),
    ],

    # -----------------------------------------------------------------------
    # 4. Диверсифицированный FX без IRS (4 пары + 1 своп)
    #    Инструменты: 0 IRS + 4 FX Forward + 1 FX Swap, 0% IRS
    #    Ожидаемая корреляция: низкая — разные валютные пары, разные драйверы
    # -----------------------------------------------------------------------
    "fx_diversified": [
        usdrub_fwd("FWD USDRUB 1M",  FWD_1M, rate=87.20),
        eurrub_fwd("FWD EURRUB 3M",  FWD_3M, rate=95.40, direction=Direction.SELL),
        cnyrub_fwd("FWD CNYRUB 6M",  FWD_6M, rate=11.85),
        eurusd_fwd("FWD EURUSD 3M",  FWD_3M, rate=1.0840),
        usdrub_swap("SWAP USDRUB 3M"),
    ],
}

# ---------------------------------------------------------------------------
# Сохранение
# ---------------------------------------------------------------------------

def main():
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_portfolios')
    os.makedirs(out_dir, exist_ok=True)
    exporter = PortfolioExporter(JsonSerializer())
    for name, instruments in PORTFOLIOS.items():
        path = os.path.join(out_dir, f"{name}.json")
        data = exporter.save(instruments)
        with open(path, 'wb') as f:
            f.write(data)
        irs_count = sum(1 for i in instruments if isinstance(i, InterestRateSwap))
        print(f"  {name}.json  —  {len(instruments)} инстр., {irs_count} IRS ({irs_count*100//len(instruments)}%)")
    print(f"\nПортфели сохранены в {os.path.abspath(out_dir)}")


if __name__ == '__main__':
    main()
