import pandas as pd
from iolib.serializers.base import BaseSerializer
from iolib.serializers.csv_serializer import CsvSerializer
from iolib.serializers.excel_serializer import ExcelSerializer


class ResultsExporter:
    def __init__(self, serializer: BaseSerializer) -> None:
        self._serializer = serializer

    def export(self, data: dict) -> bytes:
        if isinstance(self._serializer, CsvSerializer):
            return self._export_csv(data)
        if isinstance(self._serializer, ExcelSerializer):
            return self._export_excel(data)
        # JSON / YAML — serialize everything, DataFrames converted to dict
        return self._serializer.serialize(self._to_serializable(data))

    def _export_csv(self, data: dict) -> bytes:
        """Export only the first DataFrame in the dict."""
        for value in data.values():
            if isinstance(value, pd.DataFrame):
                return self._serializer.serialize(value)
        return b""

    def _export_excel(self, data: dict) -> bytes:
        """Each DataFrame gets its own sheet; scalars go to a Summary sheet."""
        sheets: dict = {}
        scalars: dict = {}
        for key, value in data.items():
            if isinstance(value, pd.DataFrame):
                sheets[key] = value
            else:
                scalars[key] = value
        if scalars:
            sheets["Summary"] = pd.DataFrame(
                [{"metric": k, "value": v} for k, v in scalars.items()]
            )
        return self._serializer.serialize(sheets)

    @staticmethod
    def _to_serializable(data: dict) -> dict:
        result = {}
        for key, value in data.items():
            if isinstance(value, pd.DataFrame):
                result[key] = value.reset_index().to_dict(orient="records")
            else:
                result[key] = value
        return result
