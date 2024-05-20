from datetime import datetime
from pathlib import Path
from typing import Union

from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.case_insensitive_dict import CaseInsDict


PathLike = Union[str, Path]

TimeLike = Union[float, datetime]