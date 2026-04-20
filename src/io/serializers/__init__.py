from .json_serializer import JsonSerializer
from .yaml_serializer import YamlSerializer
from .csv_serializer import CsvSerializer
from .excel_serializer import ExcelSerializer

SERIALIZERS: dict = {
    "json":  JsonSerializer(),
    "yaml":  YamlSerializer(),
    "csv":   CsvSerializer(),
    "excel": ExcelSerializer(),
}

FORMAT_LABELS = list(SERIALIZERS.keys())  # ["json", "yaml", "csv", "excel"]
