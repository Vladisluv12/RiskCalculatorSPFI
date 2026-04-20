import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from datetime import datetime
from instruments.BaseInstrument import Direction, CurrencyPair
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from io.serializers.json_serializer import JsonSerializer
from io.serializers.yaml_serializer import YamlSerializer
from io.serializers.csv_serializer import CsvSerializer
from io.serializers.excel_serializer import ExcelSerializer
from io.portfolio_io import PortfolioImporter, PortfolioExporter


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
