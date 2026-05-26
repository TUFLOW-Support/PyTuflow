import logging
import io
import os.path
import typing
from pathlib import Path
from typing import TextIO, OrderedDict
from uuid import uuid4

from ..abc.input import T_Input, Input
from ..inp.inp_build_state import InputBuildState
from ..inp.inp_run_state import InputRunState
from ..inp.altered_input import AlteredInput
from ..inp.comment import CommentInput
from ..inp.inputs import Inputs
from ..inp.trd import TuflowReadFileInput
from ..tfpathlib import TuflowPath
from ..tmf_types import PathLike
from ..db.db_build_state import DatabaseBuildState
from ..abc.cf import ControlFile
from ..abc.bld_state import BuildState
from ..tfstrings.increment_number import increment_fpath, get_iter_number
from ..tfstrings.geom_suffix import get_geom_suffix
from ..settings import TCFConfig
from ..parsers.command import Command
from ..parsers.non_recursive_basic_parser import get_commands
from ..scope_writer import ScopeWriter
from ..inp.altered_input import AlteredInputs
from ..inp.get_input_class import get_input_class
from ..scope import ScopeList
from ..context import Context
from ..scope import Scope

from .. import const


if typing.TYPE_CHECKING:
    from .cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class ControlFileBuildState(BuildState, ControlFile):
    """Initialises the class in a build state.

    If the class is initialised with the ``fpath`` parameter set to None, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file. If set to None, will initialise an empty control file.

    **kwargs : optional parameters

        - config : TCFConfig, optional
            This object stores useful information such as variable mappings, the event database,
            current spatial database etc. If set to None, a new TCFConfig object will be created.
            For TCFs, the settings object should be left as None.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a TGC, the parent
            should be set to the TCF. For TCFs, the parent should be set to None.
        - scope : ScopeList, optional
            A list of scope objects that will be inherited by the control file itself. Not currently used
            but reserved in case this is useful information in the future.
        - log_level : str, optional
            The logging level to use for the control file. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'WARNING'.
        - log_to_file : PathLike, optional
            If set, will log the control file to the given file path. Default is None.
    """
    TUFLOW_TYPE = 'ControlFile'

    def __init__(self,
                 path: PathLike = None,
                 config: TCFConfig = None,
                 parent: ControlFile = None,
                 scope: ScopeList = None,
                 **kwargs) -> None:
        super(BuildState, self).__init__()
        #: TCFConfig: The configuration settings for the model.
        self.config = TCFConfig.from_tcf_config(config) if config is not None else TCFConfig()
        if path is not None:
            self.config.control_file = Path(path)
        #: Inputs: The list of inputs and comments in the control file
        self.inputs = Inputs[InputBuildState]()
        #: ControlFile: The parent control file
        self.parent = parent
        #: AlteredInputs: The list of all changes made to the control file since the last time :meth:`write` was called.
        self.altered_inputs = AlteredInputs()
        #: bool: Whether the control file has been loaded from disk or not.
        self.loaded = False

        self._fpath = Path(path).resolve() if path is not None else None
        self._dirty = False
        self._active_trd = None  # the active TRD file that is being loaded
        self._active_trd_inp = None
        self._scope = scope if scope is not None else ScopeList()
        
        if self.fpath:
            try:
                self._load(path)
                self.loaded = True
            except FileNotFoundError:
                pass

    def __repr__(self):
        return f'<{self.TUFLOW_TYPE}> {str(self)}'

    def __str__(self):
        if self.fpath:
            if self.loaded:
                return self.fpath.name
            else:
                return f'{self.fpath.name} (not found)'
        return 'Empty Control File'

    @property
    def fpath(self) -> Path:
        """Path: The path to the control file."""
        return self._fpath

    @fpath.setter
    def fpath(self, value: PathLike):
        value = Path(value)
        self._fpath = value
        self.config.control_file = value
        if self.TUFLOW_TYPE == const.CONTROLFILE.TCF:
            self.config.tcf = value
            for inp in self.inputs:
                inp.config.control_file = value
                inp.tcf = self.config.tcf
                for cf in inp.cf:
                    cf.config.tcf = self.config.tcf
                    if inp.TUFLOW_TYPE == const.INPUT.CF:
                        for inp1 in cf.inputs:
                            inp1.config.tcf = self.config.tcf

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'ControlFileRunState':
        # docstring inherited
        from .cf_run_state import ControlFileRunState
        ctx = context if context else Context(run_context, config=self.config)
        return ControlFileRunState(self, ctx, parent)

    def figure_out_file_scopes(self, scope_list: ScopeList) -> None:
        """no-doc

        Overrides abstract method from BuildState.

        Try and resolve unknown scope variable values based on a known scope list. Not currently connected to anything
        (previously was connected to the load method).

        This method is designed to trickle through all
        BuildState objects and figure out scope definitions when scenarios/variables are used in the file names, and the
        scope is guessed based on the file name and any files it found

        e.g. ``M01_<<s1>>_001.tgc`` - ``M01_5m_001.tgc`` - would guess that the file
        has a ``Scope(Scenario, '5m')``

        Parameters
        ----------
        scope_list: ScopeList
            list of known scopes
        """
        for input_ in self.inputs:
            input_.figure_out_file_scopes(scope_list)

    def record_change(self, inputs: Inputs | DatabaseBuildState, change_type: str):
        """no-doc

        Record a user change to the inputs.

        Not private, but should not be called by the user.

        Parameters
        ----------
        inputs : Inputs
            A list of inputs that have been changed.
        change_type : str
            the type of change that has been made. This is used to determine what to do when storing and
            undoing the change. See AlteredInputs class for change_type options.
        """
        uuid = uuid4()  # allows input changes to be grouped together by giving the same uuid
        if isinstance(inputs, Inputs):
            for inp, ind in inputs.iter_indexes():
                inp.dirty = True
                self.dirty = True
                self.tcf.dirty = True
                self.tcf.altered_inputs.add(inp, ind[0], ind[1], uuid, change_type)
        elif isinstance(inputs, DatabaseBuildState):
            self.tcf.altered_inputs.add(inputs, -1, -1, uuid, 'database')

    def undo(self, include_children: bool = True) -> list[AlteredInput]:
        """Undo the last recorded change. Recorded changes are automatically stored when inputs are changed, added,
        or removed from the control file. The :attr:`dirty` attribute can be checked to see if any changes have
        been made to the control file since the last call to :meth:`write`.

        Note, the returned list of inputs is stored as a :class:`AlteredInput`, which is different from the
        input class used to store the inputs in the control file.

        Parameters
        ----------
        include_children : bool, optional
            This is only applicable for the TCF class. If set to ``True``, will undo the last change regardless if it
            was made in the current control file or a child. If set to ``False``, will only undo the
            last change in the current control file.

        Returns
        -------
        list[AlteredInput]
            A list of inputs that were changed by the undo operation. If no
            changes were made, an empty list is returned.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code comments out the SGS input then uses the ``undo`` method to revert the change:

        >>> cf = ... # assume this is the loaded control file object
        >>> sgs_inp = cf.find_input('SGS == On')[0]
        >>> cf.comment_out(sgs_inp)
        <CommentInput> ! SGS == On

        Preview the content of the control file to confirm that the SGS input has been commented out:

        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == GPU
        ! SGS == On

        Undo the previous operation to uncomment the SGS input:

        >>> cf.undo()
        [<AlteredInput comment_out> ! SGS == On]
        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On
        """
        if self.tcf != self and include_children:
            include_children = False
        return self.tcf.altered_inputs.undo(self, include_children)

    def reset(self, include_children: bool = True) -> list[AlteredInput]:
        """Resets all recorded changes made to the control file since the last call to :meth:`write`.
        Recorded changes are automatically stored when inputs are changed, added,
        or removed from the control file. The :attr:`dirty` attribute can be checked to see if any changes have
        been made to the control file since the last call to :meth:`write`.

        Note, the returned list of inputs are stored as :class:`AlteredInput`, which is different from the
        input class used to store the inputs in the control file.

        Parameters
        ----------
        include_children : bool
            Only applicable for the TCF class. If set to ``True``, will reset changes regardless of whether they
            were made in the current control file or a child. If set to ``False``, will only reset the
            changes in the current control file.

        Returns
        -------
        list[AlteredInput]
            A list of inputs that were reset by the reset operation. If no
            changes were made, an empty list is returned.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code comments out the SGS input and sets the hardware command to ``CPU``.
        It then uses the ``reset`` method to revert all the changes:

        >>> cf = ... # assume this is the loaded control file object
        >>> sgs_inp = cf.find_input('SGS == On')[0]
        >>> cf.comment_out(sgs_inp)
        <CommentInput> ! SGS == On
        >>> hardware_inp = cf.find_input('Hardware == GPU')[0]
        >>> hardware_inp.rhs = 'CPU'

        Preview the content of the control file to confirm that the SGS input has been commented out and the
        hardware input has been changed to ``CPU``:

        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == CPU
        ! SGS == On

        Reset all operations to take the control file back to its original state:

        >>> cf.reset()
        [<AlteredInput update_value> Hardware == GPU, <AlteredInput comment_out> ! SGS == On]
        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On

        """
        if self.tcf != self and include_children:
            include_children = False
        return self.tcf.altered_inputs.reset(self, include_children)

    def remove_input(self, inp: InputBuildState) -> InputBuildState | None:
        """Removes the input from the control file.

        Parameters
        ----------
        inp : InputBuildState
            The input to remove from the control file.

        Returns
        -------
        InputBuildState
            The input that was removed. If the method returns ``None``, no input was removed.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code removes the SGS input from the control file:

        >>> control_file = ... # assume this is the loaded control file object
        >>> sgs_inp = control_file.find_input('SGS == On')[0]
        >>> control_file.remove_input(sgs_inp)
        <SettingInput> SGS == On

        The content of the control file can be previewed using :meth:`preview` to confirm
        that the SGS command has been removed:

        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == GPU
        """
        if inp in self.inputs:
            inputs = Inputs()
            inputs.append(inp)
            self.inputs.remove(inp)
            self.record_change(inputs, 'remove_input')
            if self.tcf and self.tcf != self:
                self.tcf.record_change(inputs, 'remove_input')
            return inp
        else:
            for inp1 in self.inputs:
                if inp1.TUFLOW_TYPE == const.INPUT.CF and inp1.cf:
                    for cf in inp.cf:
                        inp2 = cf.remove_input(inp)
                        if inp2:
                            return inp2
        return None

    def append_input(self, input_text: str | T_Input, gap: int = 0) -> T_Input:
        """Appends a new input to the end of the control file.

        Parameters
        ----------
        input_text : str | T_Input
            The input text to add to the control file (i.e. the TUFLOW command). Leading whitespace will be
            respected. However, the input will be indented automatically depending on its scope and generally
            is not required to be considered by the user in the input text.

            Alternatively, an existing input instance can be passed in. If the input does not already exist
            in the control file, the input instance will be added directly. If the input already exists within
            the control file, a copy of the input will be made and added.
        gap : int, optional
            The number of blank lines to add before the new input. This has no impact on the TUFLOW model, but
            can be useful for readability of the control file when it is written to disk. Default is 0.

        Returns
        -------
        T_Input
            The input that was added. The input type will be determined by the ``input_text`` string e.g. if the
            text is ``Read GIS Z Shape == ...``, then the return input will be of type :class:`GisInput`.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Sceme == HPC
           Hardware == GPU

        The following code appends a new input to the end of the control file:

        >>> cf = ... # assume this is the loaded control file object
        >>> inp = cf.append_input('SGS == On')
        >>> inp
        <SettingInput> SGS == On

        The content of the control file can be previewed using :meth:`preview`:

        >>> cf.preview()
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On

        The new input is not written to disk until :meth:`write` is called. :meth:`undo` can be used
        to revert the last change made to the control file, which in this case would remove the new command.
        """
        return self._add_input(None, input_text, True, gap)

    def insert_input(self, ref_inp: T_Input, input_text: str | T_Input, after: bool = False, gap: int = 0) -> InputBuildState:
        """Inserts an input before, or after, another reference input.

        Parameters
        ----------
        ref_inp : InputBuildState
            The input to place the new command before, or after.
        input_text : str
            The input text to add to the control file (i.e. the TUFLOW command). Leading whitespace will be
            respected. However, the input will be indented automatically depending on its scope and generally
            is not required to be considered by the user in the input text.

            Alternatively, an existing input instance can be passed in. If the input does not already exist
            in the control file, the input instance will be added directly. If the input already exists within
            the control file, a copy of the input will be made and added.
        after : bool, optional
            If True, the new input will be inserted after the referenced input, if set to False, the new
            input will be inserted before. Default is False.
        gap : int, optional
            The number of blank lines to add before, or after (depending on the ``after`` parameter),
            the new input. This has no impact on the TUFLOW model, but can be useful for readability
            of the control file when it is written to disk. Default is 0.

        Returns
        -------
        InputBuildState
            The input that was added. The input type will be determined by the ``input_text`` string e.g. if the
            text is ``Read GIS Z Shape == ...``, then the return input will be of type :class:`GisInput`.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Hardware == GPU
           SGS == On

        The following code inserts a new input to the top of the control file, before the first input:

        >>> cf = ... # assume this is the loaded control file object
        >>> inp = cf.inputs[0]
        >>> new_inp = cf.insert_input(inp, 'Solution Scheme == HPC')
        >>> ref_inp
        <SettingInput> Solution Scheme == HPC

        The content of the control file can be previewed using :meth:`preview`:

        >>> cf.preview()
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On

        The new input is not written to disk until :meth:`write` is called. :meth:`undo` can be used
        to revert the last change made to the control file, which in this case would remove the new command.
        """
        return self._add_input(ref_inp, input_text, after, gap)

    def comment_out(self, inp: InputBuildState) -> CommentInput:
        """Comments out a given input. This has the same effect as :meth:`remove_input`, but keeps the input
        in the control file as a comment. The input can be uncommnented later using the :meth:`uncomment` method.
        Comments can also still be searched for within the control file using the :meth:`find_input` method.

        The input is not mutated, rather a new input is created and replaces the original input in the control file.
        Further reference to the input should use the returned input. The commented out input
        retains the same UUID.

        Parameters
        ----------
        inp : InputBuildState
            The input to comment out.

        Returns
        -------
        CommentInput
            The commented out input.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code comments out the SGS input:

        >>> cf = ... # assume this is the loaded control file object
        >>> sgs_inp = cf.find_input('SGS == On')[0]
        >>> commented_inp = cf.comment_out(sgs_inp)
        >>> commented_inp
        <CommentInput> ! SGS == On

        The content of the control file can be previewed using :meth:`preview`:

        >>> cf.preview()
        Solution Scheme == HPC
        Hardware == GPU
        ! SGS == On

        The new input is not written to disk until :meth:`write` is called. :meth:`undo` can be used
        to revert the last change made to the control file, which in this case would be to uncomment the given input.
        """
        new_inp = self._comment_out(inp)
        inputs = Inputs()
        inputs.append(new_inp)
        self.record_change(inputs, 'comment_out')
        if self.tcf and self.tcf != self:
            self.tcf.record_change(inputs, 'comment_out')
        return new_inp

    def uncomment(self, inp: CommentInput) -> InputBuildState:
        """Uncomment a given input.

        The input is not mutated, rather a new input is created and replaces the original input in the control file.
        Further reference to the input should use the returned input. The new input
        retains the same UUID as the original input.

        Parameters
        ----------
        inp : CommentInput
            the input to uncomment

        Returns
        -------
        InputBuildState
            The new input

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           ! SGS == On

        The following code uncomments the SGS input:

        >>> cf = ... # assume this is the loaded control file object
        >>> commented_inp = cf.find_input('sgs == on', comments=True)[0]
        >>> cf.uncomment(commented_inp)
        <SettingInput> SGS == On

        The content of the control file can be previewed using :meth:`preview` to confirm that the SGS input
        has been uncommented:

        >>> cf.preview()
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On
        """
        new_inp = self._uncomment(inp)
        inputs = Inputs()
        inputs.append(new_inp)
        self.record_change(inputs, 'uncomment')
        if self.tcf and self.tcf != self:
            self.tcf.record_change(inputs, 'uncomment')
        return new_inp

    def write(self, inc: str | None = 'auto') -> 'ControlFileBuildState':
        """Write the object to file. From the TCF class, other control files will also be written if
        their ``dirty`` attribute is returned as ``True``.

        Parameters
        ----------
        inc : str, optional
            The increment method to use. The options are:

            * ``"auto"`` - (default) automatically increment the file name by adding +1 to the number at the end of the file name.
              If the file name does not contain a number, it will be added as "001". The increment number from the
              calling class will be used when writing children. E.g. if the TCF is automatically incremented to
              "100", the TGC increment number will be set to "100" regardless of the current number
              in the TGC file name.
            * ``[str]`` - a user defined suffix to add to the file name. This will replace the existing suffix number if
              the user provides a string representation of a number, otherwise it will be appended to the end of
              the file name.
            * ``"inplace"`` - overwrites the existing file without changing the file name. If called from the TCF,
              the children control files and databases can still be incremented up to the TCF increment number.
            * ``None`` - if set to None, no incrementing will take place and the file will be written without
               changing the file name, including children control files and databases. This is very similar
               to the "inplace" option, but will not increment the file name of children control files and databases.

        Returns
        -------
        ControlFileBuildState
            The control file that was written.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code updates the hardware command to ``CPU`` and then writes the update to disk inplace such
        that it overwrites the existing control file:

        >>> control_file = ... # assume this is the loaded control file object
        >>> hardware_inp = control_file.find_input('Hardware')[0]
        >>> hardware_inp.rhs = 'CPU'
        >>> control_file.write('inplace')
        """
        if not self.fpath or self.fpath == Path():
            inc = 'inplace'

        self_fpath = increment_fpath(self.fpath, inc)
        geom_ext = get_geom_suffix(self_fpath.stem)
        inc_children = inc if inc is None else get_iter_number(self_fpath.stem, geom_ext)
        if inc == 'inplace' and not inc_children:
            inc_children = 'inplace'

        # write children first so that path references are updated
        for inp in self.find_input(callback=lambda x: x.TUFLOW_TYPE in [const.INPUT.CF, const.INPUT.DB]):
            if inp.dirty:
                for cf in inp.cf:
                    cf.write(inc_children)
                inp.rhs = increment_fpath(inp.rhs, inc_children)

        inputs, trds = self._get_trd_inputs(self)

        # write trd files
        for fpath, d_inputs in trds.items():
            trd_inputs = d_inputs['inputs']
            ref_inp = d_inputs['inpref']
            if not fpath.exists() or any(x.dirty for x in trd_inputs):
                if fpath.exists():  # only increment name if the file already exists
                    trd_fpath = increment_fpath(fpath, inc_children)
                    ref_inp.rhs = increment_fpath(ref_inp.rhs, inc_children)  # update reference to TRD file
                else:
                    trd_fpath = fpath
                with open(trd_fpath, 'w') as fo:
                    self._write(fo, trd_inputs)
                for inp in trd_inputs:
                    inp.trd = trd_fpath

        # write self
        with self_fpath.open('w') as fo:
            self._write(fo, inputs)

        self.fpath = self_fpath
        self.loaded = True
        self.altered_inputs.clear()
        return self

    def preview(self, buf: TextIO | None = None):
        """Preview the control file in ``stdout``. This method is useful for debugging and
        checking the control file content without writing it to disk.

        Parameters
        ----------
        buf : TextIO, optional
            If provided, the control file will be written to this TextIO object instead of ``stdout``.
            If not provided, the control file will be printed to ``stdout``.

        Examples
        --------
        .. code-block:: tuflow
           :linenos:

           ! Control File
           Solution Scheme == HPC
           Hardware == GPU
           SGS == On

        The following code loads and then previews the content of the control file:

        >>> cf = ... # assume this is the loaded control file object
        >>> cf.preview()
        ! Control File
        Solution Scheme == HPC
        Hardware == GPU
        SGS == On
        """
        fo = buf if buf else io.StringIO()
        inputs, _ = self._get_trd_inputs(self)
        self._write(fo, inputs)
        if not buf:
            print(fo.getvalue())

    def add_variable(self, variable_name: str, variable_value: str):
        """no-doc

        Adds a variable to the TCFConfig settings object. This change is propagated to children.
        """
        super().add_variable(variable_name, variable_value)
        for inp in self.inputs:
            inp.add_variable(variable_name, variable_value)
            for cf in inp.cf:
                cf.add_variable(variable_name, variable_value)

    def remove_variable(self, variable_name: str):
        """no-doc

        Removes a variable from the TCFConfig settings object. This change is propagated to children.
        """
        super().remove_variable(variable_name)
        for inp in self.inputs:
            inp.remove_variable(variable_name)
            for cf in inp.cf:
                cf.remove_variable(variable_name)

    def _load(self, path: PathLike) -> None:
        """Loads control file from path - loops through commands in control file.
        Called by :meth:`__init__ <pytuflow.tmf.ControlFileBuildState.__init__>`.

        This method should not be called by the user.

        Parameters
        ----------
        path : PathLike
            The path to the control file. If set to None, will initialise an empty control file.
        """
        p = TuflowPath(path)
        if not p.exists():
            logger.error('Control file not found: {}'.format(path))
            raise FileNotFoundError(f'Control file not found: {p}')
        logger.info('Loading control file at: {}'.format(p))

        if not self.config:
            self.config = TCFConfig(p)

        for command in get_commands(p, self.config):
            self._append_input(command, self._active_trd, self._active_trd_inp)

    @staticmethod
    def _get_trd_inputs(cf: 'ControlFileBuildState') -> tuple[Inputs, dict[Path, dict[str, Inputs | T_Input]]]:
        """Get the inputs that are in TRD files from the control file.
        This method returns a list of input from the control file without inputs that are in TRD files and with the
        "Read File == " input inserted. It also returns a dictionary with the TRD file paths keys and the
        corresponding inputs as values.
        """
        d = OrderedDict()
        ret_inputs = Inputs()
        for inp in cf.inputs.inputs(include_hidden=True):
            if inp.trd is not None:
                if inp.trd not in d:
                    d[inp.trd] = {}
                    d[inp.trd]['inputs'] = Inputs()
                    rel_path = os.path.relpath(inp.trd, cf.fpath.parent)
                    trd_inp = TuflowReadFileInput(cf, Command(f'Read File == {rel_path}', inp.config, line_number=inp.line_number))
                    d[inp.trd]['inpref'] = trd_inp
                    ret_inputs.append(trd_inp)
                d[inp.trd]['inputs'].append(inp)
            else:
                ret_inputs.append(inp)

        return ret_inputs, d

    @staticmethod
    def _write(fo: TextIO, inputs: Inputs):
        scope_writer = ScopeWriter()
        for inp, scope_writer_ in scope_writer.inputs(fo, inputs):
            inp.write(fo, scope_writer_)

    def _load_trd(self, inp: InputBuildState):
        """Inputs in read files are loaded into the current control file."""
        self._active_trd_inp = inp
        for file in inp.files:
            self._active_trd = file
            try:
                self._load(file)
            except FileNotFoundError:
                pass
        self._active_trd = None
        self._active_trd_inp = None

    def _append_input(self, cmd: Command, trd: TuflowPath | None, trd_input: T_Input | None) -> InputBuildState:
        inp = get_input_class(cmd)(self, cmd)
        if inp.command().is_read_file():
            if trd is not None:
                logger.error(f'Nested TRD files are currently not supported. Command: {inp}')
                raise ValueError(f'Nested TRD files are currently not supported. Command: {inp}')
            self._load_trd(inp)
            return inp
        self.inputs.append(inp)
        inp.trd = trd
        inp.trd_input = trd_input
        self.config.spatial_database = cmd.config.spatial_database
        self.config.spatial_database_tcf = cmd.config.spatial_database_tcf
        return inp

    def _insert_input(self, ind: int, cmd: Command, trd: TuflowPath | None, after: bool, hidden_index: bool = False) -> InputBuildState:
        inp = get_input_class(cmd)(self, cmd)
        if self.inputs.inputs(include_hidden=True) and len(self.inputs.inputs(include_hidden=True)) > ind:
            self.inputs.insert(ind, inp, after, hidden_index)
        else:
            self.inputs.append(inp)
        inp.trd = trd
        self.config = cmd.config
        if inp.command().is_read_file():  # special treatment of read files
            self._load_trd(inp)
        return inp

    def _add_input(self, inp: T_Input | None, input_text: str | T_Input, after: bool = True, gap: int = 0) -> InputBuildState:
        """
        Adds a new input to the control file.

        Parameters
        ----------
        inp : InputBuildState | None
            The input to place the new command after or before. If None, the new command will be added
            to the end of the control file.
        input_text : str
            String with the full command
        after : bool
            True to place the new command after the referenced input, False to place before
        gap : int
            The number of blank lines to add before this command (or after if `after` is True).

        Returns
        -------
        InputBuildState
            The input that was added to the control file.
        """
        # check if input is in another control file if the current control file is a TCF
        if inp and inp not in self.inputs.inputs(include_hidden=True) and self.TUFLOW_TYPE == const.CONTROLFILE.TCF:
            for inp1 in self.inputs:
                if inp1.TUFLOW_TYPE == const.INPUT.CF and inp1.cf:
                    for cf in inp.cf:
                        inp2 = cf.insert_input(inp, input_text, after, gap)
                        if inp2:
                            return inp2
            logger.error(f'Input {inp} not found in control file inputs. Cannot add input {input_text}.')
            raise ValueError(f'Input {inp} not found in control file inputs. Cannot add input {input_text}.')

        if inp is None:  # get the last input (i.e. append to the end of the control file) if inp is None
            index = max(0, len(self.inputs.inputs(include_hidden=True)) - 1)
            try:
                inp = self.inputs.at_index(index, include_hidden=True)
            except IndexError:  # no inputs in the control file
                inp = None
        else:
            index = self.inputs.index(inp, include_hidden=True)

        # config should be taken from previous input in-case the next input after is a 'Spatial Database ==' command
        if not inp:
            config = self.config
        elif after:
            config = inp.config
        else:
            try:
                config = self.inputs.next_before(inp).config
            except ValueError:  # no input before the specified input
                config = TCFConfig.from_tcf_config(self.config)
                if self.TUFLOW_TYPE == const.CONTROLFILE.TCF:
                    config.spatial_database = Path()
                else:
                    config.spatial_database = self.config.spatial_database_tcf

        # create the command
        cmd = Command(input_text, config) if isinstance(input_text, str) else input_text.command()
        cmd.config = config
        trd = None
        uuid = None
        scope = None
        if isinstance(input_text, Input):
            trd = input_text.trd
            if input_text.uuid not in [x.uuid for x in self.inputs.inputs(include_hidden=True)]:
                uuid = input_text.uuid
            if not uuid or isinstance(input_text, InputRunState):
                scope = input_text.scope
                input_text = str(input_text)
        inputs = Inputs()  # a container to store all the added inputs, including blank lines

        if after:  # insert blank lines before adding new input if the new input is after the specified input
            i = -1
            for i in range(gap):
                idx = index + i
                blank_inp = self._insert_input(idx, Command('\n', cmd.config), trd=None, after=after, hidden_index=True)
                inputs.append(blank_inp)
            index += i + 1

        if isinstance(input_text, InputBuildState):
            self.inputs.insert(index, input_text, after, hidden_index=True)
            inp_out = input_text
            inp_out.config = config
            inp_out.parent = self
        else:
            inp_out = self._insert_input(index, cmd, trd, after, hidden_index=True)
            if uuid:
                inp_out.uuid = uuid
            if scope:
                inp_out.scope = scope
        inputs.append(inp_out)

        if not after:  # insert blank lines after adding the new input if the new input is before the specified input
            for i in range(gap):
                blank_inp = self._insert_input(index + i + 1, Command('\n', cmd.config), trd, after, hidden_index=True)
                inputs.append(blank_inp)

        self.record_change(inputs, 'add_input')
        if self.tcf and self.tcf != self:
            self.tcf.record_change(inputs, 'add_input')

        if cmd.is_set_variable() and Scope('Scenario') not in inp_out.scope and Scope('Event') not in inp_out.scope:
            self.tcf.add_variable(*cmd.parse_variable())

        return inp_out

    @staticmethod
    def _comment_out(inp: InputBuildState) -> CommentInput:
        config = inp.command().config
        text = inp.command().original_text
        trd = inp.trd
        i = 0
        for i, t in enumerate(text):
            if t not in  [' ', '\t']:
                break
        if i == len(text) - 1:
            i = 0
        if i < 2:
            new_text = f'! {text}'
        else:
            new_text = text[:i] + '! ' + text[i:]

        new_cmd = Command(new_text, config)
        new_inp = CommentInput(inp.parent, new_cmd)
        new_inp.trd = trd
        inp.parent.inputs.amend(inp, new_inp)
        new_inp.uuid = inp.uuid
        return new_inp

    def _uncomment(self, inp: InputBuildState) -> InputBuildState:
        if inp:
            return inp  # a valid input already

        config = inp.command().config
        text = inp.command().original_text
        trd = inp.trd

        if '!' not in text and '#' not in text:
            logger.warning('Blank line')
            raise ValueError('Blank line')

        if '!' in text:
            i = text.index('!')
            if i + 1 < len(text) and text[i+1] == ' ':
                new_text = text.replace('! ', '', 1)
            else:
                new_text = text.replace('!', '', 1)
        else:
            i = text.index('#')
            if i + 1 < len(text) and text[i+1] == ' ':
                new_text = text.replace('# ', '', 1)
            else:
                new_text = text.replace('#', '', 1)

        new_cmd = Command(new_text, config)
        new_inp = get_input_class(new_cmd)(self, new_cmd)
        new_inp.trd = trd
        self.inputs.amend(inp, new_inp)
        new_inp.uuid = inp.uuid
        return new_inp
