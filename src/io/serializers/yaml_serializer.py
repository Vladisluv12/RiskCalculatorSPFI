from typing import Any
import yaml
from .base import BaseSerializer


class YamlSerializer(BaseSerializer):
    def serialize(self, data: Any) -> bytes:
        return yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False).encode("utf-8")

    def deserialize(self, raw: bytes) -> Any:
        return yaml.safe_load(raw.decode("utf-8"))

    @property
    def file_extension(self) -> str:
        return "yaml"

    @property
    def mime_type(self) -> str:
        return "application/x-yaml"
