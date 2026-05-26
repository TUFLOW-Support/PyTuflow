import logging
import re
from pathlib import Path

from .cf import ControlFile
from .tef_base import TEFBase
from ..context import Context
from ..event import EventDatabase
from ..scope import Scope
from ..tfpathlib import TuflowPath
from ..abc.input import T_Input
from ..abc.t_cf import T_ControlFile



logger = logging.getLogger('pytuflow')


class TCFBase(ControlFile):

    def __init__(self, *args, **kwargs):
        self._fpath = Path()
        super().__init__(*args, **kwargs)

    def tgc(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('geometry control file', **kwargs)

    def tbc(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('bc control file', **kwargs)

    def ecf(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('estry control file', **kwargs)

    def tscf(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('swmm control file', **kwargs)

    def bc_dbase(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('bc database', **kwargs)

    def mat_file(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('read materials? file', regex=True, regex_flags=re.IGNORECASE, **kwargs)

    def soils_file(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('read soils? file', regex=True, regex_flags=re.IGNORECASE, **kwargs)

    def rainfall_dbase(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('read grid rf', **kwargs)

    def tef(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('event file', **kwargs)

    def event_database(self, context: Context = None) -> EventDatabase:
        """Returns the EventDatabase object.

        If more than one EventDatabase object exists, a Context object must be provided to resolve to the correct
        EventDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct EventDatabase object. Not required unless more than one
            EventDatabase file object exists.

        Returns
        -------
        EventDatabase
            The EventDatabase object.

        Raises
        ------
        KeyError
            If the Event File is not found in the control file.
        ValueError
            If more than one Event File is found and no context is provided to resolve the correct one or if
            the context does not resolve into a single Event File.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.event_database()
        {'Q100': {'_event1_': '100yr'},
         'QPMF': {'_event1_': 'PMFyr'},
         '2hr': {'_event2_': '2hr'},
         '4hr': {'_event2_': '4hr'}}
        """
        tef: TEFBase = self._find_control_file('event file', context)
        return tef.event_database()

    def output_folder_1d(self, context: Context = None) -> Path:
        """Returns the 1D output folder.

        Returns the last instance of the command. If multiple versions of the output folder command exist
        and some exist in IF logic blocks, a context must be provided to resolve the correct one.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct 1D output directory. Not required unless more than one
            1D output directory exists.

        Returns
        -------
        Path
            The 1D output directory.

        Raises
        ------
        ValueError
            If the output folder cannot be determined.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.output_folder_1d()
        WindowsPath('../results/EG15')
        """
        output_folders = []
        for inp in self.find_input(lhs='output folder', recursive=True):
            if '1D' in inp.lhs.upper():
                output_folders.append(inp)
            if Scope('1D Domain') in inp.scope:
                output_folders.append(inp)
            if inp.parent and inp.parent.fpath.suffix.lower() == '.ecf':
                output_folders.append(inp)

        output_folders = self._resolve_multiple_output_folders(output_folders, context)

        if output_folders:
            return Path(output_folders[-1].value)
        try:
            return self.output_folder_2d(context)
        except ValueError:
            logger.error('No 1D or 2D output folder command found and TCF file path is not set, '
                         '1D output folder cannot be determined.')
            raise ValueError('No 1D or 2D output folder command found and TCF file path is not set, '
                             '1D output folder cannot be determined.')

    def output_folder_2d(self, context: Context = None) -> Path:
        """Returns the 2D output folder.

        Returns the last instance of the command. If multiple versions of the output folder command exist
        and some exist in IF logic blocks, a context must be provided to resolve the correct one.

        Returns the file path to the tcf file directory if the output folder command is not found.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct 2D output directory. Not required unless more than one
            1D output directory exists.

        Returns
        -------
        Path
            The 2D output directory.

        Raises
        ------
        ValueError
            If the output folder cannot be determined.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.output_folder_2d()
        WindowsPath('../results/EG15')
        """
        output_folders = []
        for inp in self.find_input(lhs='output folder', recursive=True):
            if '1D' in inp.lhs.upper():
                continue
            if Scope('1D Domain') in inp.scope:
                continue
            if inp.parent and inp.parent.fpath.suffix.lower() in ['.ecf', '.tscf']:
                continue
            output_folders.append(inp)

        output_folders = self._resolve_multiple_output_folders(output_folders, context)

        if output_folders:
            return Path(output_folders[-1].value)

        if self._fpath and self._fpath != Path():
            return self._fpath.parent

        logger.error('No output folder command found and TCF file path is not set, ')
        raise ValueError('No output folder command found and TCF file path is not set, '
                         'output folder cannot be determined.')

    def log_folder_path(self, context: Context = None) -> Path:
        """Returns the log folder path.

        Returns the last instance of the command. If more than one Log Folder exists and some exist in
        IF logic blocks an exception will be raised if a context object is also not provided.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct log folder directory. Not required unless more than one
            log folder command exists.

        Returns
        -------
        Path
            The log folder.

        Raises
        ------
        ValueError
            If the log folder cannot be determined.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.log_folder_path()
        WindowsPath('./log')
        """
        log_folders = []
        inputs = self.find_input(lhs='log folder', recursive=True)
        if len(inputs) > 1 and [x for x in inputs if Scope('GLOBAL') not in x.scope]:
            if not context:
                logger.error('{0} requires context to resolve'.format('Log Folder'))
                raise ValueError('{0} requires context to resolve'.format('Log Folder'))
            else:  # context has been provided, can try and resolve
                for i, inp in enumerate(inputs):
                    if context.in_context_by_scope(inp.scope):
                        log_folders.append(inp)
        elif inputs:
            log_folders.append(inputs[-1])

        if log_folders:
            return TuflowPath(log_folders[-1].value)

        if self._fpath and self._fpath != Path():
            return self._fpath.parent

        raise ValueError('No log folder command round and TCF file path is not set, log folder cannot be determined.')

    @staticmethod
    def _resolve_multiple_output_folders(output_folders: list[T_Input], context: Context) -> list[T_Input]:
        """Helper method to resolve multiple output folders based on the provided context."""
        if len(output_folders) > 1 and [x for x in output_folders if Scope('GLOBAL') not in x.scope]:
            if not context:
                raise ValueError('{0} requires context to resolve'.format('Output Folder'))
            else:  # context has been provided, can try and resolve
                length = len(output_folders)
                for i, inp in enumerate(reversed(output_folders[:])):
                    j = length - i - 1
                    # noinspection PyTypeChecker
                    if context.in_context_by_scope(inp.scope):
                        output_folders[i] = inp
                    else:
                        output_folders.pop(j)
        return output_folders
