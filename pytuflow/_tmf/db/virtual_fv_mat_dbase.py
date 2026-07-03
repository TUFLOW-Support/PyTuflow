import typing
import pandas as pd
import logging
from pathlib import Path

from .. import const
from .mat import MatDatabase, MatDatabaseRunState
from ..context import Context
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..misc.case_insensitive_dict import CaseInsDictOrdered
from ..parsers.fvcommand import FVSedCommand

if typing.TYPE_CHECKING:
    from ..cf.block import BlockControl
    from ..abc.fvc_base import FVCBase
    from ..cf.cf_run_state import ControlFileRunState


logger = logging.getLogger('pytuflow')


class FVMatMixin:

    @property
    def fvc(self) -> 'FVCBase':
        return self.parent.fvc if self.parent else None

    @staticmethod
    def mat_columns(fvc: 'FVCBase') -> list[str]:
        cols = [
            'Bottom Roughness',
            'Horiz Visc',
            'Horiz Visc Limits',
            'Bed Elev Limits',
            'Spatial Reconstr',
        ]
        if not fvc:
            return cols
        
        if fvc.is_3d():
            cols.append('Vert Visc Limits')

        if fvc.include_salinity() or fvc.include_temperature() or fvc.tracer_count() > 0:
            cols.extend([
                'Horiz Diffus',
                'Horiz Diffus Limits',
                'Vert Diffus Limits',
                'SW Rad Extinct Coeff'
            ])
        
        if fvc.sediment_fraction_count() > 0:
            cols.extend([
                'Suspended Load Scale',
                'Sed Nlayer'
            ])

        if fvc.wq_constituents():
            cols.extend([
                'Oxygen Flux',
                'Silicate Flux',
                'Ammonium Flux',
                'Nitrate Flux',
                'FRP Flux',
                'DOC Flux',
                'DON Flux',
                'DOP Flux'
            ])
        
        return cols
           
    
    @staticmethod
    def mat_commands(fvc: 'FVCBase') -> list[str]:
        cmds = [
            'Bottom Roughness',
            'Horizontal Eddy Viscosity',
            'Horizontal Eddy Viscosity Limits',
            'Bed Elevation Limits', 
            'Spatial Reconstruction'
        ]

        if not fvc:
            return cmds
        
        if fvc.is_3d():
            cmds.append('Vertical Eddy Viscosity Limits')
            
        if fvc.include_salinity() or fvc.include_temperature() or fvc.tracer_count() > 0:
            cmds.extend([
                'Horizontal Scalar Diffusivity',
                'Horizontal Scalar Diffusivity Limits',
                'Vertical Scalar Diffusivity Limits',
                'Short Wave Radiation Extinction Coefficients'
            ])

        if fvc.sediment_fraction_count() > 0:
            cmds.extend([
                'Suspended Load Scale',
                'Nlayers'
            ])
            
        if fvc.wq_constituents():
            cmds.extend([
                'Oxygen Flux',
                'Silicate Flux',
                'Ammonium Flux',
                'Nitrate Flux',
                'FRP Flux',
                'DOC Flux',
                'DON Flux',
                'DOP Flux'
            ])
        
        return cmds
        
    
    @staticmethod
    def global_mat_commands(fvc: 'FVCBase') -> list[str]:
        return [f'Global {x}' for x in FVMatMixin.mat_commands(fvc)]
    
    def create_dataframe(self, mat_classes: list['_Mat']):
        d = {x: [] for x in ['ID'] + FVMatMixin.mat_columns(self.fvc)}
        for mat_class in mat_classes:
            entry = mat_class.bc_dbase_entry()
            count = 1
            for lst in entry.values():
                count = len(lst) if isinstance(lst, list) else 1
                break
            default = ['' for _ in range(count)]
            for name, lst in d.items():
                v = entry.get(name, default)
                if name == 'Name':
                    if isinstance(v, list):
                        for n in v:
                            self.item2mat_class[n] = mat_class
                    else:
                        self.item2mat_class[v] = mat_class
                lst.extend(v) if isinstance(v, list) else lst.append(v)
                
        df = pd.DataFrame(d)
        self.df = df.set_index('ID')


class _Mat(FVMatMixin):

    def __init__(self, parent: 'VirtualFVMatDatabase', id: int | str, controls: list['BlockControl']):
        self.parent = parent
        self.resolved = True
        self.controls = controls
        self.parent_inputs = [x.parent_input for x in self.controls if hasattr(x, 'parent_input')]
        self.id = id

    def __repr__(self):
        return f'<{self.__class__.__name__}> {str(self.parent_inputs)}'
    
    @staticmethod
    def supports_value_extraction() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        d = {'ID': self.id}
        d.update({x: '' for x in self.mat_columns(self.fvc)})
        has_sediment_mat = False
        for cmd, col in zip(self.mat_commands(self.fvc), self.mat_columns(self.fvc)):
            for control in self.controls:
                if isinstance(control.parent_input.command(), FVSedCommand):
                    has_sediment_mat = True
                for inp in control.find_input(lhs=cmd):
                    d[col] = inp.value
        if has_sediment_mat and d['Sed Nlayer'] == '':
            d['Sed Nlayer'] = 1
        return d
    

class _GlobalMat(_Mat):

    def bc_dbase_entry(self) -> dict:
        def is_default_mat_block(x):
            if x.TUFLOW_TYPE == const.INPUT.BLOCK and x.lhs.upper() == 'MATERIAL':
                for id_ in str(x.value).split(','):
                    if id_.strip().lower() in ['0', 'default']:
                        return True
            return False
        
        d = {'ID': self.id}
        d.update({x: '' for x in self.mat_columns(self.fvc)})

        # search for global commands
        for cmd, col in zip(self.global_mat_commands(self.fvc), self.mat_columns(self.fvc)):
            for control in self.controls:
                for inp in control.find_input(lhs=cmd):
                    d[col] = inp.value

        # search for material blocks with id 0 (zero) or 'default'
        inps = self.fvc.find_input(callback=is_default_mat_block)
        controls = [inp.block_control() for inp in inps]
        mat_class = _Mat(self.parent, self.id, controls)
        d.update(mat_class.bc_dbase_entry())

        return d


class VirtualFVMatDatabase(MatDatabase, FVMatMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fpath = self.parent.fpath if self.parent else None
        self.item2mat_class = CaseInsDictOrdered() 

    @property
    def df(self) -> pd.DataFrame:
        return MatDatabase.df.fget(self)

    @df.setter
    def df(self, value: pd.DataFrame):
        self._df = value
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=value.copy())
    
    @staticmethod
    def from_mat_controls(fvc: 'FVCBase', controls: list['BlockControl']) -> 'VirtualFVMatDatabase':
        mat_dbase = VirtualFVMatDatabase(config=fvc.config, parent=fvc)

        controls_sorted = {}
        for control in controls:
            try:
                if isinstance(control.parent_input.value, str):
                    ids = control.parent_input.value.split(',')
                elif isinstance(control.parent_input.value, (float, int)):
                    ids = [control.parent_input.value]
                else:
                    ids = control.parent_input.value
                for id_ in ids:
                    id_ = id_.strip() if isinstance(id_, str) else id_
                    if str(id_).lower() in ['0', 'default']:  # not including defaults here
                        continue
                    id_ = int(id_)
                    if id_ not in controls_sorted:
                        controls_sorted[id_] = [control]
                    else:
                        controls_sorted[id_].append(control)
            except ValueError:
                logger.error(f'Error occurred trying to convert material id to an integer on line {control.parent_input.line_number}: {control.parent_input}')
        controls_sorted = {k: controls_sorted[k] for k in sorted(controls_sorted)}
        
        mat_classes = [_GlobalMat(mat_dbase, 'DEFAULT', [fvc] if fvc else [])]
        for id_, controls in controls_sorted.items():
            mat_class = _Mat(mat_dbase, id_, controls)
            mat_classes.append(mat_class)

        mat_dbase.create_dataframe(mat_classes)
        mat_dbase.reload()

        return mat_dbase

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'VirtualFVMatDatabaseRunState':
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return VirtualFVMatDatabaseRunState(self, ctx, parent)
    
    def reload(self):
        self._load_from_df(self.df)
        self.loaded = True

    def is_plottable(self, item: str | int) -> bool:
        return False
    
    def _load(self, fpath: Path):
        # override and do nothing
        pass


class VirtualFVMatDatabaseRunState(MatDatabaseRunState):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fpath = self.parent.fpath if self.parent else None
    
    def is_plottable(self, item: str | int) -> bool:
        return False
