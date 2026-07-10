from abc import ABC, abstractmethod
from pathlib import Path


class BaseProject(ABC):
    @abstractmethod
    def create(self) -> Path: ...

    def validate(self) -> list[str]:
        return []
