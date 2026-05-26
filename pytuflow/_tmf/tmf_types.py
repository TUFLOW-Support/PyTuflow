import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .abc.cf import ControlFile
    # noinspection PyUnusedImports
    from .abc.db import Database


PathLike = str | Path
# Type hint for a context like object that can be passed into the Context class to initialise it
ContextLike = str | dict[str, str]
# Type hint for a variable map that can be passed into a Context object
VariableMap = dict[str, str] | dict[str, list[str]]

# Type hint for a search tag list item used to filter inputs from a control file. Can be in the form of a :code:`str` or a tuple :code:`(str, typing.Any)` or a list of tuples :code:`[(str, typing.Any), ...]`.
SearchTag = str | tuple[str, typing.Any] | list[typing.Any] | tuple
SearchTagLike = SearchTag | list[SearchTag] | tuple[SearchTag, ...]

#: ControlFile | Database: Type hint for a control file or database object.
ControlLike = 'ControlFile | Database'
