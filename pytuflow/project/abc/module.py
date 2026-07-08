from abc import ABC, abstractmethod


class BaseModule(ABC):
    NAME: str
    DISPLAY_NAME: str

    @abstractmethod
    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        """Returns list of (template_key, output_relative_path) pairs."""

    @abstractmethod
    def apply_to_control_files(self, control_files: dict, variables: dict) -> None:
        """Apply this module's command blocks to the supplied control file objects.

        Parameters
        ----------
        control_files : dict[str, ControlFile]
            Mapping of CF type key (``'tcf'``, ``'tgc'``, …) to the loaded
            control file build-state object.
        variables : dict
            Template variable substitutions.
        """
