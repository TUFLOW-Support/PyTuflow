from abc import ABC, abstractmethod
from pathlib import Path


class BaseProject(ABC):
    @abstractmethod
    def create(self) -> Path: ...

    @abstractmethod
    def insert_module(self, module_name: str) -> None: ...

    def validate(self) -> list[str]:
        return []
