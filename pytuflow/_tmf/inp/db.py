import logging
import typing

from .file import FileInput
from .cf import ControlFileInputRunState
from ..abc.bld_state import BuildState
from ..context import Context
from .. import const

from .. db import bc_dbase, mat, soil, pit_inlet, rf, xs


if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class DatabaseInput(FileInput):
    """Input class for database inputs.

    | e.g.
    | :code:`BC Database == bc_database.csv`
    | :code:`Read Materials File == materials.csv`
    """
    TUFLOW_TYPE = const.INPUT.DB

    @property
    def dirty(self) -> bool:
        return self._dirty or any(cf.dirty for cf in self.cf)

    @dirty.setter
    def dirty(self, value: bool):
        BuildState.dirty.fset(self, value)

    def _load(self):
        super()._load()
        self._load_files()
        self._load_database_files()
        self._file_scopes()

    def _load_files(self):
        super()._load_files()
        self._files_loaded = True

    def _load_database_files(self):
        for file in self._rhs_files:
            try:
                if self._command.is_bc_dbase_file():
                    cf = bc_dbase.BCDatabase(file, self._command.config, self.parent, self.scope)
                elif self._command.is_mat_dbase():
                    cf = mat.get_material_database_class(file)(file, self._command.config, self.parent, self.scope)
                elif self._command.is_soil_dbase():
                    cf = soil.SoilDatabase(file, self._command.config, self.parent, self.scope)
                elif self._command.is_pit_inlet_dbase_file():
                    cf = pit_inlet.PitInletDatabase(file, self._command.config, self.parent, self.scope)
                elif self._command.is_rainfall_grid():
                    if file.suffix == '.nc':
                        logger.warning('Rainfall grid files in NetCDF format (.nc) are not supported yet.')
                        cf = rf.RainfallDatabase(None)  # .nc not yet supported
                    else:
                        cf = rf.RainfallDatabase(file, self._command.config, self.parent, self.scope)
                elif self._command.is_table_link():
                    cf = xs.CrossSectionDatabase(file, self._command.config, self.parent, self.scope)
                elif self._command.is_xs_dbase():
                    cf = xs.CrossSectionDatabase(file, self._command.config, self.parent, self.scope)
                else:
                    logger.error(f'Unknown database type for {file}')
                    raise ValueError(f'Unknown database type for {file}')
                self.cf.append(cf)
            except Exception as e:
                logger.error(f'Error loading database {file}. Command: {self._command}. Error: {e}')

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> ControlFileInputRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return ControlFileInputRunState(self, ctx, parent)
