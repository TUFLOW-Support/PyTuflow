import typing
from typing import TYPE_CHECKING
from uuid import UUID

from ..scope import Scope
from ..tmf_types import SearchTagLike
from ..inp.inputs import Inputs
from ..context import Context
from .input import T_Input
from ..settings import TCFConfig
from .t_cf import ControlBase, T_ControlFile

from .. import const

if TYPE_CHECKING:
    from ..abc.input import Input


class ControlFile(ControlBase):
    """Abstract base class for all control file classes."""
    TUFLOW_TYPE = 'ControlFile'

    def __init__(self, *args, **kwargs):
        self._fpath = None
        #: ControlFile: The parent control file
        self.parent = None
        #: TCFConfig: the configuration settings for the model.
        self.config = TCFConfig()
        #: Inputs: The list of inputs and comments in the control file
        self.inputs = Inputs()

    @property
    def tcf(self):
        """ControlFile: The parent TCF control file object"""
        if not self.parent:
            return self
        else:
            tcf = self.parent
            while tcf.parent:
                tcf = tcf.parent
            return tcf

    def input(self, uuid: str | UUID) -> T_Input:
        """Returns the input with the given UUID. UUIDs remain constant across build and run state conversions.
        If the input is not found in the control file, it will search through any child control files.

        Parameters
        ----------
        uuid : str | UUID
            The UUID of the input to retrieve.

        Returns
        -------
        Input
            The input with the given UUID.

        Raises
        ------
        KeyError
            If no input with the given UUID is found in the control file or its child control files.

        Examples
        --------
        The example below finds an input and then checks if the input is still present after
        creating a run state instance of the control file.

        >>> control_file = ... # Assume the control file has been loaded
        >>> code_inp = control_file.find_input('2d_code')[0]
        >>> run_control_file = control_file.context('-s1 EXG -s2 5m')
        >>> try:
        ...     run_inp = run_control_file.input(code_inp.uuid)
        ...     print(f'Input found: {run_inp}')
        ... except KeyError:
        ...     print('Input not found in run state control file.')
        """
        if isinstance(uuid, str):
            uuid = UUID(uuid)

        for inp in self.inputs.inputs(include_hidden=True):
            if inp.uuid == uuid:
                return inp
            if self.TUFLOW_TYPE == const.CONTROLFILE.TCF and inp.TUFLOW_TYPE == const.INPUT.CF and inp.cf:
                for cf in inp.cf:
                    try:
                        inp1 = cf.input(uuid)
                        return inp1
                    except KeyError:
                        continue
        raise KeyError(f'Input with UUID {uuid} not found.')

    def find_input(self,
                   filter_by: str = None,
                   lhs: str = None,
                   rhs: str = None,
                   recursive: bool = True,
                   regex: bool = False,
                   regex_flags: int = 0,
                   attrs: SearchTagLike = (),
                   callback: typing.Callable[[T_Input], bool] = None,
                   comments: bool = False) -> list[T_Input]:
        """Find a particular input(s) using a search filter. The filter can be for the entire command,
        or specifically to the left-hand side ``lhs`` or right-hand side ``rhs`` of the command.

        The filter can be a basic search string, or it can be switched to
        be a regular expression depending on the ``regex`` parameter with regex flags
        passed in using the ``regex_flags`` parameter. If ``regex`` is set to ``False``, the filter strings will
        be case-insensitive. If ``regex`` is set to ``True``, the filter strings will be treated as
        regular expressions and the ``regex_flags`` will be used to control the matching behaviour.

        More complex rules / filtering can be done by using the ``attrs`` or ``callback`` parameters. Comments can also
        be searched through by setting the ``comments`` parameter to ``True``.

        If no filtering parameters are provided, all inputs will be returned.

        Parameters
        ----------
        filter_by : str, optional
            A string or regular expression to filter the input by.
            This will search through the entire input string (not comments).
        lhs : str, optional
            A string or regular expression to filter the input by.
            This will search through the left-hand side of the input.
        rhs : str, optional
            A string or regular expression to filter the input by.
            This will search through the right-hand side of the input.
        recursive : bool, optional
            If set to True, will also search through any child control files.
        regex : bool, optional
            If set to True, the filter, lhs, and rhs parameters will be treated as regular expressions.
        regex_flags : int, optional
            The regular expression flags to use when using regular expressions.
        attrs : SearchTagLike, optional
            A list of tags to filter the input by. The tags represent properties of the input, such as ``dirty`` or
            ``has_missing_files``. The tag can be a tuple of (tag_name, tag_value) or just a tag name where the tag
            value is assumed to be evaluated as ``True``. A single tag (tag_name, tag_value) or a list of tags
            can be provided.
        callback : Callable, optional
            A function that will be called with the input as an argument. The callback should take an
            ``T_Input`` argument and return a boolean indicating whether the input matches the filter.
        comments : bool, optional
            If set to True, will also search through the comments of the input, including lines that only contain
            comments. Note that commented out inputs are not separated into left-hand side and right-hand side,
            and the ``lhs`` and ``rhs`` parameters will not work on commented out inputs.

        Returns
        -------
        list[T_Input]
            A list of inputs that match the filter.

        Examples
        --------
        An example of a simple search to find all GIS material inputs in the model:

        >>> control_file = ... # Assume the control file has been loaded
        >>> control_file.find_input(lhs='read gis mat')
        [<GisInput> Read GIS Mat == gis\2d_mat_Roads_001_R.shp, <GisInput> Read GIS Mat == gis\2d_mat_Grass_001_R.shp]

        Extending the example above to find all material inputs using a regular expression. A regular expression needs
        to be used in the case since using the filter ``"mat"`` will return false positives. For example, it will
        return instances if the word "format" appears in the command
        (e.g. "GIS Format == ..." or "Map Output Format == ..."). It will also return the material file if
        searching from the TCF.

        >>> import re
        >>> control_file.find_input(lhs=r'(set|read gis|read grid) mat', regex=True, regex_flags=re.IGNORECASE)
        [<SettingInput> Set Mat == 1,
         <GisInput> Read GIS Mat == gis\2d_mat_Roads_001_R.shp, <GisInput> Read GIS Mat == gis\2d_mat_Grass_001_R.shp]

        An example using the ``tags`` parameter is to find all inputs that have missing files. This can be useful
        when performing any integrity or pre-modelling checks on the model inputs:

        >>> control_file.find_input(attrs=('has_missing_files', True))
        [<GisInput> Read GIS Code == gis\2d_code_EG00_001.shp]

        An example of using the ``callback`` parameter to find all inputs that use GIS polygon geometry:

        >>> from osgeo import ogr # this example requires GDAL/OGR to be installed
        >>> from pytuflow import const
        >>> control_file.find_input(callback=lambda x: x.TUFLOW_TYPE == const.INPUT.GIS and ogr.wkbPolygon in x.geoms)
        """
        inputs = self.inputs.inputs(include_hidden=comments)
        ret_inputs = []
        for inp in inputs:
            if inp.is_match(filter_by, lhs, rhs, regex, regex_flags, attrs, callback, comments):
                ret_inputs.append(inp)
            if recursive and inp.TUFLOW_TYPE == const.INPUT.CF and inp.cf:
                for cf in inp.cf:
                    ret_inputs.extend(cf.find_input(filter_by, lhs, rhs, recursive, regex, regex_flags, attrs,
                                                    callback, comments))
        return ret_inputs

    def _find_control_file(self,
                           lhs: str,
                           context: Context = None,
                           regex: bool = False,
                           regex_flags: int = 0) -> T_ControlFile:
        inputs = self.find_input(lhs=lhs, regex=regex, regex_flags=regex_flags)
        if len(inputs) > 1 or (hasattr(self, '_scope') and inputs and Scope('GLOBAL') not in inputs[0].scope):
            if context is None:
                raise ValueError('{0} requires context to resolve'.format(lhs))
            else:
                input_ = None
                for inp in inputs:
                    if context.in_context_by_scope(inp.scope):
                        if input_ is not None:
                            raise ValueError('Multiple commands found in context')
                        input_ = inp
        elif inputs:
            input_ = inputs[0]
        else:
            input_ = None

        if input_ is None:
            raise KeyError('No Control File/Database found for {0}'.format(lhs))

        loaded_value = input_.cf
        if isinstance(loaded_value, list) and loaded_value:
            if len(loaded_value) > 1:
                if context is None:
                    raise ValueError('{0} requires context to resolve'.format(lhs))
                value_tr = context.translate(input_.value)
                if value_tr in [x.fpath for x in loaded_value]:
                    value = loaded_value[[x.fpath for x in loaded_value].index(value_tr)]
                else:
                    raise ValueError('No Control File/Database found for {0} with the provided context'.format(lhs))
            else:
                value = loaded_value[0]
        elif not loaded_value:
            raise ValueError('No Control File/Database has been loaded for {0}'.format(lhs))
        else:
            value = loaded_value

        return value
