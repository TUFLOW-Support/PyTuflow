import logging
import os
import typing
import subprocess
from pathlib import Path

from .cf_run_state import ControlFileRunState
from ..abc.tcf_base import TCFBase
from ..tmf_types import PathLike
from ..tuflow_binaries import tuflow_binaries
from ..context import Context



logger = logging.getLogger('pytuflow')

if typing.TYPE_CHECKING:
    from ....._outputs.tpc import TPC
    from .tcf import TCF
    from .tef_run_state import TEFRunState
    from ..db.bc_dbase_run_state import BCDatabaseRunState
    from ..db.mat import MatDatabaseRunState
    from ..db.soil import SoilDatabase
    from ..db.db_run_state import DatabaseRunState


class TCFRunState(ControlFileRunState, TCFBase):
    """Class for storing the run state of a TCF file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the :meth:`context()<pytuflow.TCF.context>` method of the BuildState class.

    Parameters
    ----------
    build_state : TCF
        The TCF build state instance that the RunState object is based on.
    context : Context
        The context instance that will be used to resolve the build state.
    parent : ControlFileRunState
        The parent control file run state.
    """
    def __init__(self, build_state: 'TCF', context: Context, parent: ControlFileRunState | None):
        #: TCF: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: subprocess.Popen: the process that is running the TUFLOW simulation.
        self.proc = None

        self._tpc = None  # cached TPC result

        super(TCFRunState, self).__init__(build_state, context, parent)

    def tgc(self) -> ControlFileRunState:
        """Returns the model's TGC ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TGC ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the Geometry Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tgc = tcf.context().tgc()
        """
        return super().tgc()

    def tbc(self) -> ControlFileRunState:
        """Returns the model's TBC ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TBC ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the BC Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tbc = tcf.context().tbc()
        """
        return super().tbc()

    def ecf(self) -> 'ControlFileRunState':
        """Returns the model's ECF ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The ECF ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the ESTRY Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> ecf = tcf.context().ecf()
        """
        return super().ecf()

    def tscf(self) -> 'ControlFileRunState':
        """Returns the model's TSCF ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TSCF ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the SWMM Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tscf = tcf.context().tscf()
        """
        return super().tscf()

    def tef(self) -> 'TEFRunState':
        """Returns the model's TEFRunState instance.

        Returns
        -------
        TEFRunState
            The TEFRunState instance.

        Raises
        ------
        KeyError
            If the Event File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tef = tcf.context().tef()
        """
        return super().tef()

    def bc_dbase(self) -> 'BCDatabaseRunState':
        """Returns the model's BCDatabaseRunState instance.

        Returns
        -------
        BCDatabaseRunState
            The BCDatabaseRunState instance.

        Raises
        ------
        KeyError
            If the bc_dbase is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> bc_dbase = tcf.context().bc_dbase()
        """
        return super().bc_dbase()

    def mat_file(self) -> 'MatDatabaseRunState':
        """Returns the model's MatDatabaseRunState instance.

        Returns
        -------
        MatDatabaseRunState
            The MatDatabaseRunState instance.

        Raises
        ------
        KeyError
            If the material file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> mat_file = tcf.context().mat_file()
        """
        return super().mat_file()

    def soils_file(self) -> 'SoilDatabase':
        """Returns the model's SoilDatabase instance.

        Returns
        -------
        SoilDatabase
            The SoilDatabase instance.

        Raises
        ------
        KeyError
            If the soil file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> soils_file = tcf.context().soils_file()
        """
        return super().soils_file()

    def rainfall_dbase(self) -> 'DatabaseRunState':
        """Returns the model's rainfall database instance.

        Returns
        -------
        DatabaseRunState
            The rainfall database instance.

        Raises
        ------
        KeyError
            If the rainfall database file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> rainfall_dbase = tcf.context().rainfall_dbase()
        """
        return super().rainfall_dbase()

    def output_name(self) -> str:
        """Returns the file name of the result file without any extension.

        Returns
        -------
        str
            Name of the result file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG16_~s1~_~s2~_002.tcf')
        >>> tcf.context('-s1 5m -s2 EXG').output_name()
        'EG16_5m_EXG_002'
        """
        return self.ctx.translate_result_name(self.fpath.name)

    def tpc(self) -> 'TPC':
        """Returns the TPC result from the simulation.

        Returns
        -------
        TPC
            The TPC result.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tpc = tcf.context().tpc()
        >>> tpc.ids()
        ['FC01.1_R.1',
         'FC01.1_R.2',
         'FC01.2_R.1',
         ...
         'Pipe8',
         'Pipe9']
        """
        if self._tpc is not None:
            return self._tpc

        try:
            from ....._outputs.tpc import TPC
        except ImportError:
            logger.error('Cannot import TPC from pytuflow.results. This method can only used when tmf has been '
                         'installed via the PyTuflow library.')
            raise ImportError('Cannot import TPC from pytuflow.results. This method can only used when tmf has been '
                              'installed via the PyTuflow library.')
        self._tpc = TPC(self.tpc_path())
        return self._tpc

    def tpc_path(self) -> Path:
        """Returns the path to the expected tpc file. Does not check it exists.

        Returns
        -------
        Path
            File path to the tpc file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tcf.context().tpc_path()
        WindowsPath('../results/EG15/plot/EG15_001.tpc')
        """
        return (self.output_folder_2d() / 'plot' / self.output_name()).with_suffix('.tpc')

    def tlf_path(self) -> Path:
        """Returns the path to the expected tlf file. Does not check it exists.

        Returns
        -------
        Path
            File path to the tlf file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tcf.context().tlf_path()
        WindowsPath('./log/EG15_001.tlf')
        """
        return (self.log_folder_path() / self.output_name()).with_suffix('.tlf')

    def run(self, tuflow_bin: PathLike, prec: str = 'sp', add_cli_args: list[str] = (), *args, **kwargs):
        """Run the control file in context using the specified TUFLOW binary.

        * TUFLOW binary can be a file path to the executable or a version name that has been registered using
          the :func:`register_tuflow_binary function()<pytuflow.register_tuflow_binary>`
          or the :func:`register_tuflow_binary_folder()<pytuflow.register_tuflow_binary_folder>`.

        Additional arguments can be passed in and will be passed to the subprocess.Popen() call. By default,
        a new console will be created for the subprocess.

        Parameters
        ----------
        tuflow_bin : PathLike
            Path to the TUFLOW binary or a registered version name.
        prec : str, optional
            Precision of the run. Default is ``"sp"`` (single precision).
            Alternate option is ``"dp"`` (double precision) (accepted aliases ``"idp"`` and ``"double"``).
        add_cli_args : list[str]
            A list of additional command line arguments specific to TUFLOW that will be passed directly to the
            subprocess.Popen() call. e.g. ``add_cli_args=['-t']`` to pass in the ``-t`` flag to run TUFLOW in test mode,
            or ``add_cli_args=['-cs1']`` to pass in the ``-cs1`` flag to run TUFLOW with case-insensitive file paths.
        *args, **kwargs:
            Will be passed to subprocess.Popen() call.

        Returns
        -------
        subprocess.Popen
            The subprocess.Popen object that is created when the control file is run.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.context().run('2025.1.2')
        <Popen: returncode: None args: ['C:\\TUFLOW\\releases\\2025.1.2\\TUFLOW_iSP_...>
        """
        tuflow_bin_ = self._find_tuflow_bin(tuflow_bin, prec)
        return self._run(tuflow_bin_, add_cli_args, *args, **kwargs)

    def test(self, tuflow_bin: PathLike, prec: str = 'sp') -> tuple[str, str]:
        """Run the control file in context using the specified TUFLOW binary in test mode.

        The stdout and stderr are automatically captured (no console window is produced) and once complete, the
        return values are the captured stdout and stderr.

        Parameters
        ----------
        tuflow_bin : PathLike
            File path to the TUFLOW binary or a registered version name.
        prec : str, optional
            Precision of the run. Default is ``"sp"`` (single precision).
            Alternate option is to use ``"dp"`` (double precision) (accepted aliases ``"idp"`` and ``"double"``).

        Returns
        -------
        tuple[str, str]
            Captured stdout and stderr from the run.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> stdout, stderr = tcf.context().test('2025.1.2')
        >>> print(stderr)
        NoXY: ERROR 2131 - Reading parameter(s) or option for .tcf command below, or command is ambiguous.
        """
        proc = self.run(tuflow_bin, prec, add_cli_args=['-t', '-nmb'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW)
        out, err = proc.communicate()
        if isinstance(out, bytes):
            out = out.decode('utf-8')
        if isinstance(err, bytes):
            err = err.decode('utf-8')
        return out, err

    def _run(self, bin_path: str, add_tf_flags: list[str], *args, **kwargs):
        """Method for running the control file using the tuflow binary specified."""
        if 'creationflags' not in kwargs and os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
        args_ = [bin_path, '-b']
        for flag in add_tf_flags:
            if flag != '-b':
                args_.append(flag)
        args_.extend(self.ctx.context_args)
        args_.append(str(self.fpath))
        self.proc = subprocess.Popen(args_, *args, **kwargs)
        return self.proc

    @staticmethod
    def _find_tuflow_bin(tuflow_bin: PathLike, prec: str) -> str:
        """Returns the path to the TUFLOW binary to use for the run."""
        if Path(tuflow_bin).is_file() and not Path(tuflow_bin).exists():
            logger.error('tuflow binary not found: {0}'.format(tuflow_bin))
            raise FileNotFoundError('tuflow binary not found: {0}'.format(tuflow_bin))
        elif not Path(tuflow_bin).is_file():
            if tuflow_bin not in tuflow_binaries:
                # search for available tuflow versions in registered folders
                # do this only now (after checking explicitly registered binaries first)
                # just in case this is a slow step (network drives etc.)
                tuflow_binaries.check_tuflow_folders()
                if tuflow_bin not in tuflow_binaries:
                    logger.error('TUFLOW binary version not found: {0}'.format(tuflow_bin))
                    raise KeyError('TUFLOW binary version not found: {0}'.format(tuflow_bin))
        tuflow_bin_ = str(tuflow_bin) if Path(tuflow_bin).is_file() else tuflow_binaries[tuflow_bin]
        if prec.upper() in ['DP', 'IDP', 'DOUBLE']:
            p = Path(tuflow_bin_)
            if 'dp' not in p.stem.lower():
                tuflow_bin_ = p.parent / str(p.name).replace('SP', 'DP')
        elif prec.upper() not in ['SP', 'ISP', 'SINGLE']:
            logger.error('Unrecognised "prec" argument: {0}'.format(prec))
            raise AttributeError('Unrecognised "prec" argument: {0}'.format(prec))

        return tuflow_bin_
