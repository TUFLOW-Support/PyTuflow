from datetime import datetime
from pathlib import Path
from typing import Union, Iterable, Any, Dict

from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.case_insensitive_dict import CaseInsDict
from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.append_dict import AppendDict
from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.file import TuflowPath
# from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.types import SearchTagLike, ContextLike, VariableMap

#: :class:`Path` | :code:`str`: Type hint for an object that represents a file path or directory.
PathLike = Union[Path, str]

#: :code:`float | datetime`: Type hint for an object that represents a time value (relative or absolute).
TimeLike = Union[float, datetime]

#: :code:`str | Iterable[str]`: Type hint for a context like object that can be passed into the Context class to initialise it
ContextLike = Union[list[str], tuple[str, ...], dict[str, str]]

#: :code:`Dict[str, str]`: Type hint for a variable map that can be passed into a Context object
VariableMap = Dict[str, str]

#: :code:`str | Iterable[tuple[str, Any]]`: Type hint for a search tag list item used to filter inputs from a control file. Can be in the form of a :code:`str` or a tuple :code:`(str, typing.Any)` or a list of tuples :code:`[(str, typing.Any), ...]`.
SearchTagLike = Union[str, Iterable[tuple[str, Any]]]

#: PlotExtractionLocation: Type hint for the location to extract plot data for. Includes spatial or ID based inputs.
PlotExtractionLocation = Union[str, list[str], tuple[float, float], list[tuple[float, float]], None]


class FileTypeError(ValueError):
    """Raised when a file is not of the correct type."""
    pass
