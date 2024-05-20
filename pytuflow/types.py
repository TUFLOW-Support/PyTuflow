from datetime import datetime
from pathlib import Path
from typing import Union

from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.case_insensitive_dict import CaseInsDict

#: Path | str | bytes: Type hint for a string or Path object.
PathLike = Union[Path, str, bytes]

#: float | datetime: Type hint for a time-like object.
TimeLike = Union[float, datetime]
