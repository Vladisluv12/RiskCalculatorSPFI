import io
from typing import Any
import pandas as pd
from .base import BaseSerializer


class ExcelSerializer(BaseSerializer):
    def serialize(self, data: Any) -> bytes:
        buf = io.BytesIO()
        if isinstance(data, dict):
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                for sheet_name, value in data.items():
                    if isinstance(value, pd.DataFrame):
                        value.to_excel(writer, sheet_name=str(sheet_name)[:31], index=True)
                    elif isinstance(value, (int, float)):
                        pd.DataFrame({"value": [value]}).to_excel(
                            writer, sheet_name=str(sheet_name)[:31], index=False
                        )
        elif isinstance(data, list):
            pd.DataFrame(data).to_excel(buf, index=False)
        elif isinstance(data, pd.DataFrame):
            data.to_excel(buf, index=True)
        buf.seek(0)
        return buf.read()

    def deserialize(self, raw: bytes) -> list[dict]:
        buf = io.BytesIO(raw)
        df = pd.read_excel(buf, dtype=str)
        return df.where(df.notna(), None).to_dict(orient="records")

    @property
    def file_extension(self) -> str:
        return "xlsx"

    @property
    def mime_type(self) -> str:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
