import logging
import typing
import re
from pathlib import Path
from uuid import uuid4

from ..tmf_types import SearchTagLike, SearchTag
from ..parsers.command import Command
from ..settings import TCFConfig
from ..tmf_types import PathLike
from ..scope import Scope, ScopeList



logger = logging.getLogger('pytuflow')


class Input:
    """Abstract class for holding an input. An input class holds information on the input command, value, lists
    the associated files, and any other useful information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: ControlFile: The parent control file that this input belongs to.
        self.parent = None
        #: list[ControlFile | Database]: A list of control file or database objects that are loaded from this input.
        self.cf = []
        #: UUID4: A unique identifier for the input, generated when the input is created.
        self.uuid = uuid4()
        #: Path | None: The .trd file that this input is from.
        self.trd = None
        #: T_Input | None: The trd input that this input is from.
        self.trd_input = None
        #: list[Path]: A list of files associated with this input.
        self.files: list[Path]
        #: bool: Whether this input has missing files (i.e. the files do not exist).
        self.has_missing_files: bool
        #: TCFConfig: Configuration object for the input.
        self.config = TCFConfig()
        #: int: The number of parts in the input command.
        self.part_count = 1
        self._scope: ScopeList = ScopeList()
        self._rhs_files = []  # just files associated with the rhs - e.g. not files ref in gis layer
        self._command = Command('', TCFConfig())
        self._file_to_scope = {}

    def __str__(self):
        """Returns in the format of 'Command == Value' or simply 'Command' if a value does not exist."""
        if (hasattr(self, 'is_start_block') and self.is_start_block()) or (hasattr(self, 'is_end_block') and self.is_end_block()):
            return ''
        if self.lhs and self.rhs:
            if isinstance(self.rhs, list):
                return '{0} == {1}'.format(self.lhs, ' | '.join(str(v) for v in self.rhs))
            if isinstance(self.rhs, tuple):
                return '{0} == {1}'.format(self.lhs, ', '.join(str(v) for v in self.rhs))
            return '{0} == {1}'.format(self.lhs, self.rhs)
        elif self.lhs:
            return self.lhs
        return ''

    def __bool__(self):
        """Returns true if a command exists."""
        return bool(str(self))

    def __eq__(self, other):
        """Returns true if the compared commands are the same type (i.e. both GIS inputs) and the
        command and values are the same (case insensitive).
        """
        if isinstance(other, type(self)):
            return str(self).lower() == str(other).lower()
        return False

    def __hash__(self):
        """Allows inputs to be used as a key within a dictionary. Hash based on the string value of itself and an index
        value that is generated when the input class is initialised based on the time of creation. This allows inputs
        using the same syntax to both be used as keys without any conflict.
        """
        return hash(self.uuid)

    def __repr__(self):
        """Returns the class name and string value of itself. Overriden in child classes."""
        return '<{0}> {1}'.format(self.__class__.__name__, str(self))

    @property
    def lhs(self) -> str:
        """Property holding the LHS string part of :code:`Command == Value`

        Returns
        -------
        str
            The command string part of :code:`Command == Value`
        """
        return str(self._command.command_orig).strip() if self._command.command_orig else ''

    @property
    def rhs(self) -> str:
        """Property holding the value part of :code:`Command == Value`. Value can be any type, and
        should be returned as its intended type e.g. :code:`Set Code == 0` should return an integer.

        Path values will return a string. Use expanded_value for the expanded path.

        .. note::

            ES Note - this is maybe a little inconsistent - could change

        Returns
        -------
        typing.Any
            The value part of :code:`Command == Value`
        """
        return str(self._command.value_orig).strip() if self._command.value_orig else ''

    @property
    def value(self) -> typing.Any:
        """Property holding the value part of :code:`Command == Value`. Value can be any type, and
        should be returned as its intended type e.g. :code:`Set Code == 0` should return an integer.

        Path values will return a string. Use expanded_value for the expanded path.

        .. note::

            ES Note - this is maybe a little inconsistent - could change

        Returns
        -------
        typing.Any
            The value part of :code:`Command == Value`
        """
        self._command.reload_value()
        return str(self._command.value) if self._command.value else ''

    @value.setter
    def value(self, value: typing.Any):
        raise AttributeError('The "value" attribute is read-only, use "rhs" to set the value of the input.')

    @property
    def comment(self) -> str:
        return self._command.comment if self._command.comment else ''

    @property
    def scope(self) -> ScopeList:
        return self._scope

    @scope.setter
    def scope(self,
              value: ScopeList | list[Scope] | tuple[Scope, ...] | list[tuple[str, str]] | tuple[tuple[str, str], ...]):
        self._scope = value

    @property
    def line_number(self) -> int:
        """The line number of the input within the control file (starting at line one)."""
        return self._command.line_number if self._command.line_number else -1

    @line_number.setter
    def line_number(self, value: int):
        raise AttributeError('The "line_number" attribute is read-only and is set when the command is created.')

    def is_start_block(self) -> bool:
        """Returns whether this input is the start of a block.
        e.g. :code:`If Scenario == DEV` is the start of a block.

        A start of a block can be any block that starts with

        * :code:`IF  [Scenario | Event]`
        * :code:`ELSE IF  [Scenario | Event]`
        * :code:`ELSE`
        * :code:`DEFINE  [Map Output Zone | ...]`
        * :code:`Start 1D`

        Returns
        -------
        bool
            Whether the input is the start of a block.
        """
        return self._command.is_start_define()

    def is_end_block(self) -> bool:
        """Returns whether this input is the end of a block.
        e.g. :code:`End if` is the end of a block.

         An end of a block can be any block that starts with

        * :code:`END IF`
        * :code:`ELSE IF  [Scenario | Event]`
        * :code:`ELSE`
        * :code:`END DEFINE`

        Returns
        -------
        bool
            Whether the input is the end of a block.
        """
        return self._command.is_end_define() or self._command.is_else()

    def file_scope(self, file: PathLike) -> ScopeList:
        """Public function that will return the scope of a given file.

        Parameters
        ----------
        file : PathLike
            The file to get the scope of.

        Returns
        -------
        ScopeList
            The scope of the file.
        """
        return self._file_to_scope.get(str(file), ScopeList([Scope('GLOBAL', '')]))

    def is_match(self, filter_by: str = None, lhs: str = None,
                 rhs: str = None, regex: bool = False, regex_flags: int = 0, attrs: SearchTagLike = (),
                 callback: typing.Callable = None, comments: bool = False) -> bool:
        """Returns True if the input matches the search parameters, which is made of multiple parameters.

        See :meth:`find_input() <pytuflow.tmf.ControlFile.find_input>` for details on the input filters.

        Parameters
        ----------
        filter_by : str, optional
            A string or regular expression to filter the input by.
            This will search through the entire input string (not comments).
        lhs : str, optional
            A string or regular expression to filter the input by.
            This will search through the command side of the input (i.e. LHS).
        rhs : str, optional
            A string or regular expression to filter the input by.
            This will search through the value side of the input (i.e. RHS).
        regex : bool, optional
            If set to True, the filter, command, and value parameters will be treated as regular expressions.
        regex_flags : int, optional
            The regular expression flags to use when filtering by regular expressions.
        attrs : SearchTagLike, optional
            A list of attributes to filter the input by. This can be a string (single attribute key),
            or list/tuple of strings that will be used to filter the input by tag keys which
            correspond to properties contained in the input. Attributes themselves can be tuples with a
            value to compare against (key, value) otherwise the value will be assumed as True.
        callback : typing.Callable, optional
            A function that will be called with the input as an argument.
        comments : bool, optional
            If set to True, will also search through comments.

        Returns
        -------
        bool
            True if the input matches the search parameters.
        """
        if callback is not None and not callback(self):
            return False
        if not self._tag_match(attrs):
            return False
        if regex:
            return self._regex_match(filter_by, lhs, rhs, regex_flags, comments)
        return self._str_match(filter_by, lhs, rhs, comments)

    def command(self) -> Command:
        """no-doc
        Returns the command object associated with this input."""
        return self._command

    def figure_out_file_scopes(self, scope_list: ScopeList):
        """no-doc"""
        pass

    def _tag_match(self, tags: SearchTagLike) -> bool:
        if not tags:
            return True

        def array_depth(lst: typing.Iterable) -> int:
            """Returns the depth of a list. A depth of 1 means the list is flat, a depth of 2 means it contains lists,
            etc."""
            def is_bottom(a: typing.Iterable) -> bool:
                return [not isinstance(x, (list, tuple)) for x in a][0]
            dep = 1
            lst_ = lst
            while not is_bottom(lst_):
                dep += 1
                try:
                    lst_ = lst_[0]
                except (TypeError, IndexError):
                    break
            return dep

        def parse_tag(in_tag: SearchTag):
            dep = array_depth(in_tag)
            ret_tag = []
            if isinstance(in_tag, str):
                ret_tag = [(in_tag, True)]
            elif dep == 1:
                if len(in_tag) > 2:
                    logger.error('attrs is not valid, must be a list of tuples.')
                    raise ValueError('attrs is not valid, must be a list of tuples.')
                elif len(in_tag) == 1 and isinstance(in_tag[0], str):
                    ret_tag = [(in_tag[0], True)]
                elif len(in_tag) == 2:
                    ret_tag = [(in_tag[0], in_tag[1])]
                else:
                    ret_tag = []
            return ret_tag

        # try and get tags into a consistent format - list[tuple[key, value]]
        tags_depth = array_depth(tags)
        if isinstance(tags, str) or tags_depth == 1:
            tags = parse_tag(tags)
        elif tags_depth == 2:
            tags_ = []
            for i, tag in enumerate(tags):
                tags_.append(parse_tag(tag))
        else:
            raise ValueError('attrs is not valid, the maximum depth is 2, i.e. a list of tuples, but got a depth of {0}.'.format(tags_depth))

        # loop through tags and check against value
        for tag in tags:
            if not hasattr(self, tag[0]):
                return False
            if isinstance(tag[1], bool):
                if not bool(getattr(self, tag[0])) == tag[1]:
                    return False
                continue
            if isinstance(tag[1], typing.Callable):
                if not tag[1](getattr(self, tag[0])):
                    return False
                continue
            if getattr(self, tag[0]) != tag[1]:
                return False

        return True

    def _regex_match(self, filter_by: str, lhs: str, rhs: str, flags: int, comments: bool) -> bool:
        if filter_by is not None and not re.findall(filter_by, str(self), flags=flags) and (not comments or not self._command.comment or
                not re.findall(filter_by, self._command.comment, flags=flags)):
            return False
        if lhs is not None and not re.findall(lhs, str(self.lhs), flags=flags):
            return False
        if rhs is not None and not re.findall(rhs, str(self.rhs), flags=flags):
            return False
        return True

    def _str_match(self, filter_by: str, lhs: str, rhs: str, comments: bool) -> bool:
        if (filter_by is not None and filter_by.lower() not in str(self).lower() and (not comments or not self._command.comment or
                filter_by.lower() not in self._command.comment.lower())):
            return False
        if lhs is not None and lhs.lower() not in self.lhs.lower():
            return False
        if rhs is not None and str(rhs).lower() not in str(self.rhs).lower():
            return False
        return True


T_Input = typing.TypeVar("T_Input", bound=Input)
