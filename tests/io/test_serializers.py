import json
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from io.serializers.json_serializer import JsonSerializer
from io.serializers.yaml_serializer import YamlSerializer
from io.serializers.csv_serializer import CsvSerializer


def test_json_serialize_roundtrip():
    s = JsonSerializer()
    data = [{"type": "FXForward", "notional": 100000.0, "flag": True}]
    raw = s.serialize(data)
    assert isinstance(raw, bytes)
    result = s.deserialize(raw)
    assert result == data


def test_json_file_extension():
    assert JsonSerializer().file_extension == "json"


def test_json_mime_type():
    assert JsonSerializer().mime_type == "application/json"


def test_yaml_roundtrip():
    s = YamlSerializer()
    data = [{"type": "FXForward", "notional": 100000.0}]
    assert s.deserialize(s.serialize(data)) == data


def test_yaml_file_extension():
    assert YamlSerializer().file_extension == "yaml"


def test_csv_roundtrip_list_of_dicts():
    s = CsvSerializer()
    data = [{"type": "FXForward", "notional": "100000.0", "direction": "Buy"}]
    raw = s.serialize(data)
    assert isinstance(raw, bytes)
    result = s.deserialize(raw)
    assert result[0]["type"] == "FXForward"


def test_csv_serialize_dataframe():
    import pandas as pd
    s = CsvSerializer()
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    raw = s.serialize(df)
    assert b"a" in raw and b"b" in raw


def test_csv_file_extension():
    assert CsvSerializer().file_extension == "csv"
