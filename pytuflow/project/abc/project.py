from abc import ABC, abstractmethod
from pathlib import Path


class BaseProject(ABC):
    @abstractmethod
    def create(self, overwrite_behaviour: str = 'interactive') -> Path: ...

    def validate(self) -> list[str]:
        return []
