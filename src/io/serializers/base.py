from abc import ABC, abstractmethod
from typing import Any


class BaseSerializer(ABC):
    @abstractmethod
    def serialize(self, data: Any) -> bytes: ...

    @abstractmethod
    def deserialize(self, raw: bytes) -> Any: ...

    @property
    @abstractmethod
    def file_extension(self) -> str: ...

    @property
    @abstractmethod
    def mime_type(self) -> str: ...
