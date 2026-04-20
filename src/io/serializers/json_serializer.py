import json
from typing import Any
from .base import BaseSerializer


class JsonSerializer(BaseSerializer):
    def serialize(self, data: Any) -> bytes:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    def deserialize(self, raw: bytes) -> Any:
        return json.loads(raw.decode("utf-8"))

    @property
    def file_extension(self) -> str:
        return "json"

    @property
    def mime_type(self) -> str:
        return "application/json"
