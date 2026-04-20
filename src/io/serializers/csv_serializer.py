import csv
from io import StringIO
from typing import Any
import pandas as pd
from .base import BaseSerializer


class CsvSerializer(BaseSerializer):
    def serialize(self, data: Any) -> bytes:
        if isinstance(data, pd.DataFrame):
            return data.to_csv(index=True).encode("utf-8")
        # list[dict]
        if not data:
            return b""
        buf = StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
        return buf.getvalue().encode("utf-8")

    def deserialize(self, raw: bytes) -> list[dict]:
        buf = StringIO(raw.decode("utf-8"))
        return list(csv.DictReader(buf))

    @property
    def file_extension(self) -> str:
        return "csv"

    @property
    def mime_type(self) -> str:
        return "text/csv"
