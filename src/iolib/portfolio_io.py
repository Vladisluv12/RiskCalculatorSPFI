from datetime import datetime
from typing import Any

from instruments.BaseInstrument import BaseInstrument
from instruments.enums import Direction, CurrencyPair
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from iolib.serializers.base import BaseSerializer

_INSTRUMENT_TYPES = {"FXForward", "FXSwap"}


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")


def _parse_float_or_none(val: Any) -> float | None:
    if val is None or str(val).strip() in ("", "None", "none", "null"):
        return None
    return float(val)


def _parse_date(val: Any) -> datetime:
    return datetime.strptime(str(val)[:10], "%Y-%m-%d")


def _instrument_to_dict(inst: BaseInstrument) -> dict:
    if isinstance(inst, CurrencyForwardContract):
        inst_type = "FXForward"
    elif isinstance(inst, CurrencySwapContract):
        inst_type = "FXSwap"
    else:
        inst_type = type(inst).__name__
    # Include all possible fields for both instrument types (None for absent fields).
    # This is required for flat serializers (CSV/Excel) that derive columns from the first row.
    base = {
        "type": inst_type,
        "instrument_id": inst.instrument_id,
        "notional": inst.notional,
        "direction": inst.direction.value,
        "start_date": inst.start_date.strftime("%Y-%m-%d"),
        "end_date": inst.end_date.strftime("%Y-%m-%d"),
        "currency_pair": None,
        "base_currency": None,
        "quote_currency": None,
        # FXForward-specific
        "forward_rate": None,
        "spot_rate": None,
        "is_ndf": None,
        # FXSwap-specific
        "fixed_sum_currency": None,
        "fixed_sum": None,
        "swap_points": None,
        "reverse_rate": None,
    }
    if isinstance(inst, CurrencyForwardContract):
        base.update({
            "currency_pair": inst.currency_pair.value,
            "base_currency": inst.base_currency,
            "quote_currency": inst.quote_currency,
            "forward_rate": inst.forward_rate,
            "spot_rate": inst.spot_rate,
            "is_ndf": inst.is_ndf,
        })
    elif isinstance(inst, CurrencySwapContract):
        base.update({
            "currency_pair": inst.currency_pair.value,
            "base_currency": inst.base_currency,
            "quote_currency": inst.quote_currency,
            "spot_rate": inst.spot_rate,
            "fixed_sum_currency": inst.fixed_sum_currency,
            "fixed_sum": inst.fixed_sum,
            "swap_points": inst.swap_points,
            "reverse_rate": inst.reverse_rate,
        })
    return base


def _dict_to_instrument(d: dict) -> BaseInstrument:
    inst_type = d.get("type")
    if inst_type not in _INSTRUMENT_TYPES:
        raise ValueError(f"Unknown instrument type: {inst_type!r}")
    common = dict(
        instrument_id=str(d["instrument_id"]),
        notional=float(d["notional"]),
        direction=Direction(str(d["direction"])),
        start_date=_parse_date(d["start_date"]),
        end_date=_parse_date(d["end_date"]),
        currency_pair=CurrencyPair(str(d["currency_pair"])),
        base_currency=str(d["base_currency"]),
        quote_currency=str(d["quote_currency"]),
    )
    if inst_type == "FXForward":
        return CurrencyForwardContract(
            **common,
            forward_rate=float(d["forward_rate"]),
            spot_rate=_parse_float_or_none(d.get("spot_rate")),
            is_ndf=_parse_bool(d.get("is_ndf", False)),
        )
    # FXSwap
    return CurrencySwapContract(
        **common,
        fixed_sum_currency=str(d["fixed_sum_currency"]),
        fixed_sum=float(d["fixed_sum"]),
        spot_rate=float(d["spot_rate"]),
        swap_points=int(float(d["swap_points"])),
        reverse_rate=_parse_float_or_none(d.get("reverse_rate")),
    )


class PortfolioExporter:
    def __init__(self, serializer: BaseSerializer) -> None:
        self._serializer = serializer

    def save(self, portfolio: list[BaseInstrument]) -> bytes:
        return self._serializer.serialize([_instrument_to_dict(i) for i in portfolio])


class PortfolioImporter:
    def __init__(self, serializer: BaseSerializer) -> None:
        self._serializer = serializer

    def load(self, raw: bytes) -> tuple[list[BaseInstrument], list[str]]:
        records = self._serializer.deserialize(raw)
        if not isinstance(records, list):
            records = [records]
        instruments: list[BaseInstrument] = []
        errors: list[str] = []
        for i, record in enumerate(records):
            try:
                instruments.append(_dict_to_instrument(record))
            except Exception as exc:
                errors.append(f"Row {i}: {exc}")
        return instruments, errors
