import os
import typing
from pathlib import Path

from .expand_tuflow_value import TuflowValueExpander
from ..tfpathlib import TuflowPath
from ..tfstrings.patterns import globify

if typing.TYPE_CHECKING:
    from ..settings import TCFConfig, _ParseContext


class TuflowLine:

    def __init__(self, line: str, config: 'TCFConfig | _ParseContext', parent: Path = None, *args, **kwargs):
        from ..settings import TCFConfig
        self.original_text = line
        self.config = TCFConfig.from_tcf_config(config)  # make a copy to preserve a snapshot of the config at this point
        self.parent = parent if parent else config.control_file
        self.part_count = 1
        self.part_index = -1
        self.value = self.original_text.strip()
        self.value_expanded_path = self.value  # This will be expanded later
        self._expander = TuflowValueExpander(self.config.variables, self.config.spatial_database)

    def __repr__(self):
        return self.original_text

    def expand(self, text: str) -> str:
        """Expands the line - inserts variables and expands GPKG layer names to include the relative path
        to the database.

        Does not expand relative paths.
        """
        return self._expander.expand(text)

    def expand_paths(self) -> str:
        """Expand relative paths in the text."""
        return self._expander.expand_path(self.parent, self)

    def is_number(self, text: str, total_parts: int, index: int) -> bool:
        ext = Path(text).suffix
        if ext:
            try:
                float(ext)
                return True
            except ValueError:
                return False
        try:
            float(text)
            return True
        except ValueError:
            return False

    def is_file(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text is a file path."""
        return not self.is_number(text, total_parts, index) and not self.is_folder(text, total_parts, index)

    def is_folder(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text is a folder path."""
        return False

    def should_add_mif_extension(self, text: str, total_parts: int, index: int) -> bool:
        """Adds the .mif extension to the text if it is a GIS file."""
        return False

    def looks_like_gpkg_layer_name(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text looks like a GPKG layer name."""
        return False

    def iter_files(self):
        if self.parent is None or self.parent == Path():
            return
        parent = self.parent.parent
        if self.is_file(self.value, self.part_count, self.part_index) or self.is_folder(self.value, self.part_count, self.part_index):
            try:
                rel_path = os.path.relpath(self.value_expanded_path, parent)
            except ValueError:
                if TuflowPath(self.value_expanded_path).anchor != TuflowPath(self.parent.parent).anchor:
                    parent = TuflowPath(self.value_expanded_path).anchor
                    rel_path = os.path.relpath(self.value_expanded_path, parent)
                else:
                    rel_path = self.value
        else:
            rel_path = TuflowPath(self.value)
        rel_path = globify(rel_path, self.config.wildcards)
        try:
            for file in TuflowPath(parent).glob(rel_path):
                yield file
        except Exception as e:
            # allow exception to propogate, but add additional context
            raise Exception(f"Error iterating files for line '{self.original_text}' with expanded path '{self.value_expanded_path}': {e}") from e
