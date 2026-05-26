import re
import typing
from pathlib import Path

import numpy as np

from .line import TuflowLine

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..settings import TCFConfig


class DBLine(TuflowLine):

    def __init__(self, line: str, config: 'TCFConfig', parent: Path, *args, **kwargs):
        super().__init__(line, config, parent, *args, **kwargs)
        self._parts = self.split(line)
        self.part_count = kwargs.get('part_count', len(self._parts))
        self.part_index = kwargs.get('part_index', -1)
        self.value = self.expand(self.original_text)
        self.value_expanded_path = self.expand_paths()

    def __bool__(self) -> bool:
        try:
            float(self.value)
            return not np.isnan(self.value)
        except (ValueError, TypeError):
            return bool(self.original_text.strip())

    def parts(self) -> typing.Generator['DBLine', None, None]:
        for i, p in enumerate(self._parts):
            yield DBLine(p, self.config, self.parent, part_count=self.part_count, part_index=i)

    @staticmethod
    def split(text: str) -> list[str]:
        parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', text)
        return [p.strip() for p in parts]
