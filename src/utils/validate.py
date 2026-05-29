from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime

from instruments.BaseInstrument import BaseInstrument
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap

# ── Таблицы ограничений ──────────────────────────────────────────────────────

_FWD_MIN_NOTIONAL: dict[str, int] = {
    'USD/RUB': 1_000,
    'EUR/RUB': 1_000,
    'EUR/USD': 1_000,
    'CNY/RUB': 1_000,
}

# Максимальный срок (USD/EUR — 10 лет, CNY — 5 лет; Приложение 2, Спецификация НКЦ ред. 3)
_FWD_MAX_TENOR_DAYS: dict[str, int] = {
    'USD/RUB': 3_650,
    'EUR/RUB': 3_650,
    'EUR/USD': 3_650,
    'CNY/RUB': 1_825,
}

_FWD_NDF_ALLOWED: set[str] = {'USD/RUB', 'EUR/RUB', 'CNY/RUB'}

_FWD_RATE_HINTS: dict[str, tuple[float, float]] = {
    'USD/RUB': (50.0, 200.0),
    'EUR/RUB': (50.0, 250.0),
    'EUR/USD': (0.5, 2.5),
    'CNY/RUB': (5.0, 30.0),
}

_SWAP_MAX_TENOR_DAYS = 1_095  # 3 года

_IRS_MIN_NOTIONAL: dict[str, int] = {
    'RUB': 1_000_000,
    'USD': 10_000,
    'EUR': 10_000,
    'CNY': 100_000,
}

_IRS_MIN_TENOR_DAYS = 28       # 1 месяц
_IRS_MAX_TENOR_DAYS = 10_950   # 30 лет

_TIMING_MIN_DAYS: dict[str, int] = {
    'Ежемесячно':     28,
    'Ежеквартально':  84,
    'Каждые полгода': 168,
    'Ежегодно':       365,
    'В конце периода': 1,
}

# Допустимые плавающие индексы по валюте (строки .value из FloatingIndex)
_IRS_INDEX_BY_CURRENCY: dict[str, set[str]] = {
    'RUB': {'RUONIA Avg.', 'RUONIA Comp.', 'RUSFAR RUB 3m', 'RusFar RUB O/N', 'RUB KeyRate'},
    'USD': {'SOFR Comp.'},
    'EUR': {'ESTR Comp.', 'Euribor EUR 1m', 'Euribor EUR 3m', 'Euribor EUR 6m'},
    'CNY': {'RUSFARCNY Comp.'},
}

_IRS_RECOMMENDED_DCC: dict[str, str] = {
    'RUB': 'ACT/365',
    'EUR': 'ACT/360',
    'USD': 'ACT/360',
    'CNY': 'ACT/365',
}


# ── Результат валидации ──────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


# ── Публичный интерфейс ──────────────────────────────────────────────────────

def validate(instrument: BaseInstrument, valuation_date: date | None = None) -> ValidationResult:
    """Валидирует инструмент; dispatches к приватной функции по типу."""
    if isinstance(instrument, CurrencyForwardContract):
        return _validate_fx_forward(instrument)
    if isinstance(instrument, CurrencySwapContract):
        return _validate_fx_swap(instrument, valuation_date or date.today())
    if isinstance(instrument, InterestRateSwap):
        return _validate_irs(instrument, valuation_date or date.today())
    return ValidationResult()


# ── Приватные валидаторы ─────────────────────────────────────────────────────

def _as_date(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


def _validate_fx_forward(inst: CurrencyForwardContract) -> ValidationResult:
    r = ValidationResult()
    pair_str = inst.currency_pair.value
    start = _as_date(inst.start_date)
    end   = _as_date(inst.end_date)

    if not inst.instrument_id or not inst.instrument_id.strip():
        r.errors.append("Идентификатор инструмента не может быть пустым.")

    if inst.notional <= 0:
        r.errors.append("Номинальная сумма должна быть больше нуля.")
    else:
        min_n = _FWD_MIN_NOTIONAL.get(pair_str, 1_000)
        if inst.notional < min_n:
            r.errors.append(
                f"Номинальная сумма {inst.notional:,.0f} {inst.base_currency} ниже допустимого "
                f"минимума для пары {pair_str}: {min_n:,} {inst.base_currency} "
                "(Приложение 2, Спецификация НКЦ)."
            )

    if inst.forward_rate <= 0:
        r.errors.append("Форвардный курс должен быть больше нуля.")

    if end <= start:
        r.errors.append(
            f"Дата платежа ({end}) должна быть строго позже даты расчёта ({start})."
        )
    else:
        tenor = (end - start).days
        max_tenor = _FWD_MAX_TENOR_DAYS.get(pair_str, 3_650)
        max_years = 5 if max_tenor <= 1_825 else 10
        if tenor > max_tenor:
            r.errors.append(
                f"Срок договора {tenor} дн. превышает максимально допустимый для пары "
                f"{pair_str}: {max_years} лет ({max_tenor} дн.) (Приложение 2, Спецификация НКЦ)."
            )

    if inst.is_ndf and pair_str not in _FWD_NDF_ALLOWED:
        r.errors.append(
            f"Расчётный форвард (NDF) недопустим для пары {pair_str}. "
            "Для данной пары доступен только поставочный форвард (DF)."
        )

    if inst.forward_rate > 0 and pair_str in _FWD_RATE_HINTS:
        lo, hi = _FWD_RATE_HINTS[pair_str]
        if not (lo <= inst.forward_rate <= hi):
            r.warnings.append(
                f"Форвардный курс {inst.forward_rate:.4f} для пары {pair_str} выглядит "
                f"нетипичным (ожидаемый диапазон: {lo}–{hi}). Проверьте корректность значения."
            )

    return r


def _validate_fx_swap(inst: CurrencySwapContract, valuation_date: date) -> ValidationResult:
    r = ValidationResult()
    start = _as_date(inst.start_date)
    end   = _as_date(inst.end_date)

    if not inst.instrument_id or not inst.instrument_id.strip():
        r.errors.append("Идентификатор инструмента не может быть пустым.")

    if inst.fixed_sum <= 0:
        r.errors.append("Номинал (сумма в базовой валюте) должен быть больше нуля.")

    if inst.spot_rate <= 0:
        r.errors.append("Спот-курс должен быть больше нуля.")

    fwd = inst.spot_rate + inst.swap_points * 0.0001
    if fwd <= 0:
        r.errors.append(
            f"Итоговый форвардный курс far leg (спот + пункты × 0.0001 = {fwd:.4f}) "
            "должен быть строго больше нуля. Скорректируйте спот-курс или своп-пункты."
        )

    if start < valuation_date:
        r.errors.append(
            f"Дата near leg ({start}) не может быть раньше даты оценки ({valuation_date})."
        )

    if end <= start:
        r.errors.append(
            f"Дата far leg ({end}) должна быть строго позже даты near leg ({start}). "
            "Минимальный срок свопа — 1 день."
        )
    else:
        tenor = (end - start).days
        if tenor > _SWAP_MAX_TENOR_DAYS:
            r.errors.append(
                f"Срок свопа ({tenor} дн.) превышает максимально допустимый — "
                f"3 года ({_SWAP_MAX_TENOR_DAYS} дн.) на МосБирже."
            )

    if inst.fixed_sum_currency != inst.base_currency:
        r.errors.append(
            f"Валюта фиксированной суммы ({inst.fixed_sum_currency}) не соответствует "
            f"базовой валюте пары ({inst.currency_pair.value}). "
            f"Ожидалась: {inst.base_currency}."
        )

    return r


def _validate_irs(inst: InterestRateSwap, valuation_date: date) -> ValidationResult:
    r = ValidationResult()
    currency_str = inst.currency.value
    start = _as_date(inst.start_date)
    end   = _as_date(inst.end_date)

    if not inst.instrument_id or not inst.instrument_id.strip():
        r.errors.append("ID инструмента не может быть пустым.")

    if not (0.0 <= inst.fixed_rate <= 1.0):
        r.errors.append(
            f"Фиксированная ставка ({inst.fixed_rate * 100:.2f}%) должна быть "
            "в диапазоне от 0% до 100%."
        )

    if inst.notional <= 0:
        r.errors.append("Номинал должен быть больше нуля.")
    else:
        min_n = _IRS_MIN_NOTIONAL.get(currency_str, 0)
        if inst.notional < min_n:
            r.errors.append(
                f"Номинал для валюты {currency_str} должен быть не менее "
                f"{min_n:,} {currency_str}."
            )

    if start < valuation_date:
        r.errors.append(
            f"Дата начала ({start}) не может быть раньше даты оценки ({valuation_date})."
        )

    if end <= start:
        r.errors.append(
            f"Дата окончания ({end}) должна быть позже даты начала ({start})."
        )
    else:
        tenor = (end - start).days
        if tenor < _IRS_MIN_TENOR_DAYS:
            r.errors.append(
                f"Минимальный срок свопа — 1 месяц ({_IRS_MIN_TENOR_DAYS} дн.). "
                f"Текущий срок: {tenor} дн."
            )
        elif tenor > _IRS_MAX_TENOR_DAYS:
            r.errors.append(
                f"Максимальный срок свопа — 30 лет ({_IRS_MAX_TENOR_DAYS} дн.). "
                f"Текущий срок: {tenor} дн."
            )

    if not (-500.0 <= inst.floating_spread <= 500.0):
        r.errors.append(
            f"Спред плавающей ноги ({inst.floating_spread:.1f} bp) должен быть "
            "в диапазоне от −500 до +500 bp."
        )

    allowed = _IRS_INDEX_BY_CURRENCY.get(currency_str, set())
    if inst.floating_index.value not in allowed:
        r.errors.append(
            f"Индекс «{inst.floating_index.value}» несовместим с валютой {currency_str}."
        )

    if end > start:
        tenor = (end - start).days
        for leg_label, timing in (
            ('Плавающая нога', inst.floating_payment_timing.value),
            ('Фиксированная нога', inst.fixed_payment_timing.value),
        ):
            min_days = _TIMING_MIN_DAYS.get(timing, 1)
            if tenor < min_days:
                r.errors.append(
                    f"{leg_label}: частота «{timing}» требует срок не менее {min_days} дн. "
                    f"(текущий срок: {tenor} дн.)."
                )

    rec_dc = _IRS_RECOMMENDED_DCC.get(currency_str, '')
    if rec_dc:
        float_dc = inst.floating_day_count.value
        fixed_dc = inst.fixed_day_count.value
        if float_dc != rec_dc:
            r.warnings.append(
                f"Плавающая нога ({inst.floating_index.value}): стандартная конвенция дней "
                f"для {currency_str} — {rec_dc}. "
                f"Выбрано: {float_dc}. Убедитесь, что это соответствует условиям сделки."
            )
        if fixed_dc != rec_dc:
            r.warnings.append(
                f"Фиксированная нога: стандартная конвенция дней для {currency_str} — {rec_dc}. "
                f"Выбрано: {fixed_dc}. Убедитесь, что это соответствует условиям сделки."
            )

    return r
