import json
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from io.serializers.json_serializer import JsonSerializer


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
