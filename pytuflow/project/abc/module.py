from abc import ABC, abstractmethod


class BaseModule(ABC):
    NAME: str
    DISPLAY_NAME: str

    @abstractmethod
    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        """Returns list of (template_key, output_relative_path) pairs."""

    @abstractmethod
    def apply_to_tcf(self, tcf, variables: dict) -> None:
        """Modify the loaded TCF object to add this module's commands."""
