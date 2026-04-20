import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pandas as pd
from io.serializers.json_serializer import JsonSerializer
from io.serializers.yaml_serializer import YamlSerializer
from io.serializers.csv_serializer import CsvSerializer
from io.serializers.excel_serializer import ExcelSerializer
from io.results_exporter import ResultsExporter


RESULTS = {
    "pnl": pd.DataFrame({"price": [-0.01, 0.02, -0.005]}),
    "var": 0.0234,
    "es": 0.0312,
}


def test_export_json_returns_bytes():
    raw = ResultsExporter(JsonSerializer()).export(RESULTS)
    assert isinstance(raw, bytes)
    assert b"var" in raw


def test_export_yaml_returns_bytes():
    raw = ResultsExporter(YamlSerializer()).export(RESULTS)
    assert isinstance(raw, bytes)


def test_export_csv_returns_main_dataframe():
    raw = ResultsExporter(CsvSerializer()).export(RESULTS)
    assert isinstance(raw, bytes)
    assert b"price" in raw
    # CSV export should NOT include scalar values as a table
    assert b"var" not in raw


def test_export_excel_returns_bytes():
    raw = ResultsExporter(ExcelSerializer()).export(RESULTS)
    assert isinstance(raw, bytes)
    assert len(raw) > 100  # non-empty xlsx
