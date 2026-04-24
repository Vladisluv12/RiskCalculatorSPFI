import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from datetime import datetime
from instruments.enums import Direction, CurrencyPair, Currency, DayCountConvention, PaymentTiming, OffsetRule, FloatingIndex
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap
from iolib.serializers.json_serializer import JsonSerializer
from iolib.serializers.yaml_serializer import YamlSerializer
from iolib.serializers.csv_serializer import CsvSerializer
from iolib.serializers.excel_serializer import ExcelSerializer
from iolib.portfolio_io import PortfolioImporter, PortfolioExporter


FWD = CurrencyForwardContract(
    instrument_id="FWD-001",
    notional=100000.0,
    direction=Direction.BUY,
    start_date=datetime(2025, 4, 11),
    end_date=datetime(2025, 5, 11),
    currency_pair=CurrencyPair.USD_RUB,
    base_currency="USD",
    quote_currency="RUB",
    forward_rate=95.0,
    spot_rate=None,
    is_ndf=True,
)

SWAP = CurrencySwapContract(
    instrument_id="SWAP-001",
    notional=100000.0,
    direction=Direction.SELL,
    start_date=datetime(2025, 4, 13),
    end_date=datetime(2025, 7, 13),
    currency_pair=CurrencyPair.USD_RUB,
    base_currency="USD",
    quote_currency="RUB",
    fixed_sum_currency="USD",
    fixed_sum=100000.0,
    spot_rate=92.5,
    swap_points=220,
    reverse_rate=92.522,
)

PORTFOLIO = [FWD, SWAP]


def _roundtrip(serializer):
    exporter = PortfolioExporter(serializer)
    importer = PortfolioImporter(serializer)
    raw = exporter.save(PORTFOLIO)
    instruments, errors = importer.load(raw)
    assert errors == [], f"Unexpected errors: {errors}"
    assert len(instruments) == 2
    fwd = next(i for i in instruments if isinstance(i, CurrencyForwardContract))
    assert fwd.instrument_id == "FWD-001"
    assert fwd.notional == 100000.0
    assert fwd.direction == Direction.BUY
    assert fwd.currency_pair == CurrencyPair.USD_RUB
    assert fwd.forward_rate == 95.0
    assert fwd.is_ndf is True
    swap = next(i for i in instruments if isinstance(i, CurrencySwapContract))
    assert swap.instrument_id == "SWAP-001"
    assert swap.swap_points == 220


def test_roundtrip_json():
    _roundtrip(JsonSerializer())


def test_roundtrip_yaml():
    _roundtrip(YamlSerializer())


def test_roundtrip_csv():
    _roundtrip(CsvSerializer())


def test_roundtrip_excel():
    _roundtrip(ExcelSerializer())


def test_import_skips_invalid_rows():
    importer = PortfolioImporter(JsonSerializer())
    raw = b'[{"type": "FXForward", "instrument_id": "X"}, {"type": "UNKNOWN"}]'
    instruments, errors = importer.load(raw)
    assert len(errors) == 2   # FXForward missing required fields, UNKNOWN unknown type
    assert len(instruments) == 0


# --- IRS serialization ---


def _make_irs():
    return InterestRateSwap(
        instrument_id='IRS-001',
        notional=1_000_000.0,
        direction=Direction.BUY,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2026, 1, 1),
        currency=Currency.RUB,
        fixed_rate=0.16,
        fixed_day_count=DayCountConvention.ACT_365,
        fixed_payment_timing=PaymentTiming.QUARTERLY,
        fixed_offset_rule=OffsetRule.NONE,
        floating_index=FloatingIndex.RUONIA_COMP,
        floating_spread=0.0,
        floating_day_count=DayCountConvention.ACT_365,
        floating_payment_timing=PaymentTiming.QUARTERLY,
        floating_offset_rule=OffsetRule.NONE,
    )


def test_irs_export_produces_bytes():
    irs = _make_irs()
    raw = PortfolioExporter(JsonSerializer()).save([irs])
    assert isinstance(raw, bytes)
    assert len(raw) > 0


def test_irs_roundtrip_json():
    irs = _make_irs()
    raw = PortfolioExporter(JsonSerializer()).save([irs])
    loaded, errors = PortfolioImporter(JsonSerializer()).load(raw)
    assert errors == []
    assert len(loaded) == 1
    result = loaded[0]
    assert isinstance(result, InterestRateSwap)
    assert result.instrument_id == 'IRS-001'
    assert result.currency == Currency.RUB
    assert abs(result.fixed_rate - 0.16) < 1e-9
    assert result.floating_index == FloatingIndex.RUONIA_COMP
    assert result.fixed_payment_timing == PaymentTiming.QUARTERLY
    assert result.direction == Direction.BUY


def test_mixed_portfolio_roundtrip():
    """FXForward + IRS in same portfolio serializes and deserializes correctly."""
    fwd = CurrencyForwardContract(
        instrument_id='FWD-001',
        notional=100_000.0,
        direction=Direction.BUY,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 6, 1),
        currency_pair=CurrencyPair.USD_RUB,
        base_currency='USD',
        quote_currency='RUB',
        forward_rate=90.0,
        spot_rate=None,
        is_ndf=False,
    )
    irs = _make_irs()
    raw = PortfolioExporter(JsonSerializer()).save([fwd, irs])
    loaded, errors = PortfolioImporter(JsonSerializer()).load(raw)
    assert errors == []
    assert len(loaded) == 2
    types = {type(inst).__name__ for inst in loaded}
    assert types == {'CurrencyForwardContract', 'InterestRateSwap'}
