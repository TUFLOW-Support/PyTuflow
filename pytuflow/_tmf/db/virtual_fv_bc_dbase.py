import typing
from pathlib import Path
from collections import OrderedDict
import logging
import pandas as pd
import re
import numpy as np
import sys
import inspect

from .bc_dbase import BCDatabase
from .bc_dbase_run_state import BCDatabaseRunState
from ..context import Context
from ..misc.case_insensitive_dict import CaseInsDictOrdered
from .fv_bc_dbase_entry import FVBCDatabaseEntry
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..settings import from_config
from ..abc.bld_state import BuildState


if typing.TYPE_CHECKING:
    from ..cf.block import BCBlockControl
    from ..abc.fvc_base import FVCBase
    from ..cf.cf_run_state import ControlFileRunState


logger = logging.getLogger('pytuflow')


class _BC:
    
    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        self.parent = parent
        self.resolved = True
        
        self.parent_input = control.parent_input
        self.control = control
        self.include_primary = True  # needed so it can be turned off for mass flux boundaries
        self.include_salinity = include_salinity
        self.include_temperature = include_temperature
        self.nsed = nsed
        self.ntracer = ntracer
        self.wq_constituents = wq_constituents
        self.nwq = len(self.wq_constituents)

        self.bc_header = self.default_column_names()
        self.bc_count = len(self.bc_header) - 1  # number of expected columns
        self.bc_default = [np.nan for _ in range(self.bc_count)]
        self.bc_scale = [1. for _ in range(self.bc_count)]
        self.bc_offset = [0. for _ in range(self.bc_count)]
        self.bc_update_interval = 0.

        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        self.id = rhs[1] if len(rhs) > 0 else ''
        self.modifiers = []

        self.initialise_headers()

    def __repr__(self):
        return f'<{self.__class__.__name__}> {str(self.parent_input)}'
    
    @staticmethod
    def supports_value_extraction() -> bool:
        return True
    
    @staticmethod
    def is_temporal() -> bool:
        return True
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        """Returns list of default bc column names that are expected in the source file, excluding the "Time" column."""
        raise NotImplementedError
    
    @staticmethod
    def boundary_type_name() -> str:
        """Returns the name of the boundary type e.g. "WL"."""
        raise NotImplementedError
    
    def is_modifier(self) -> bool:
        return False
    
    def add_modifier(self, bc_mod: '_BC'):
        """Adds it to the list of modifiers - does not apply anything. Called from the modifier class.."""
        raise NotImplementedError
    
    def apply_modifier(self, orig_val: pd.DataFrame | float, mod_val: pd.DataFrame | float):
        raise NotImplementedError
    
    def default_column_names(self) -> list[str]:
        """Returns a complete list of the default column names, including columns for salinity, temp, sed, tracer, and wq."""
        names = ['TIME'] + self.default_bc_column_names()
        if self.include_salinity:
            names.append('SAL')
        if self.include_temperature:
            names.append('TEMP')
        for n in range(self.nsed):
            names.append(f'SED_{n+1}')
        for n in range(self.ntracer):
            names.append(f'TRACE_{n+1}')
        for n in range(self.nwq):
            names.append(f'WQ_{n+1}')
        return names
    
    def additional_column_names(self) -> list[str]:
        """Returns the list of column names that are additional to Time,Value
        
        e.g.

        WLS has 2 value columns - Time, WL_A, WL_B. This routine would return ['WL_B']

        Additional column names should never grow with wq, tracer etc.
        """
        return []
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return True
    
    def has_sub_type(self) -> bool:
        return len(self.control.find_input(lhs='sub-type')) > 0
    
    def sub_type(self) -> int:
        for inp in self.control.find_input(lhs='sub-type'):
            try:
                return int(inp.value)
            except (ValueError, TypeError):
                logger.warning(f'Error trying to convert {inp.value} to an int')
        return -1
    
    def initialise_headers(self):
        if self.parent and self.parent.fvc:
            self.bc_update_interval = self.parent.fvc.bc_default_update_dt()
        
        for inp in self.control.find_input(lhs='bc update dt'):
            try:
                self.bc_update_interval = float(inp.value)
            except (ValueError, TypeError):
                self.bc_update_interval = inp.value

        # Headers
        self._init_headers('Header', self.bc_header)
        self._init_headers('Default', self.bc_default)
        self._init_headers('Scale', self.bc_scale)
        self._init_headers('Offset', self.bc_offset)

    def bc_dbase_entry(self) -> dict:
        """Returns bc_dbase entry(ies). Items such as salinity, temp, sed, tracer, and wq each get their own line per constituent"""
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[2]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    
    def _init_headers(self, command: str, headers: list):
        def process_header_command(command_: str, headers_: list, i: int):
            header_cmds = self.control.find_input(lhs=command_)
            for header_cmd in header_cmds:
                for scope in header_cmd.scope:
                    if scope.is_else():
                        self.resolved = False
            if header_cmds:
                header_cmd = header_cmds[-1]
                if isinstance(header_cmd.value, str):
                    header = [x.strip() for x in header_cmd.value.split(',')]
                elif isinstance(header_cmd.value, (list, tuple)):
                    header = list(header_cmd.value)
                else:
                    header = [header_cmd.value]
                j = len(header)
                headers_[i:j] = header

        idx = 0
        process_header_command(f'BC {command}', headers, idx)
        idx += len(self.default_bc_column_names())
        if self.include_salinity:
            idx += 1
        if self.include_temperature:
            idx += 1

        if self.nsed > 0:
            process_header_command(f'Sed {command}', headers, idx)
            idx += self.nsed

        if self.ntracer > 0:
            process_header_command(f'Trace {command}', headers, idx)
            idx += self.ntracer

        if self.nwq > 0:
            process_header_command(f'WQ {command}', headers, idx)
    
    @staticmethod
    def _combine_entry(entry1: dict, entry2: dict) -> dict:
        if not entry2:
            return entry1
        if not entry1:
            return entry2
        d = {x: [] for x in entry1.keys()}
        d.update({x: [] for x in entry2.keys()})
        for k, v in d.items():
            e1 = entry1.get(k, '')
            v.extend(e1) if isinstance(e1, list) else v.append(e1)
            e2 = entry2.get(k, '')
            v.extend(e2) if isinstance(e2, list) else v.append(e2)
        return d
    
    def _create_entry(self, name: str, type_: str, source: str, time_header: str, source_header_index: int) -> dict:
        d = {'Name': name, 'Type': type_}
        if source:
            d['Source'] = source
        if time_header:
            d['Column 1'] = time_header
        if source_header_index > -1:
            d['Column 2'] = self.bc_header[source_header_index]
            d['BC Scale'] = self.bc_scale[source_header_index - 1]
            d['BC Offset'] = self.bc_offset[source_header_index - 1]
            d['Default Value'] = self.bc_default[source_header_index - 1]
        return d
    
    def _bc_dbase_entry(self, name: str, type_: str, source: str, time_header: str, start_header_index: int):
        header_index = start_header_index
        d = {}
        if self.include_primary:
            d = self._create_entry(name, type_, source, time_header, header_index)
            header_index += 1
        if self.include_salinity:
            d1 = self._create_entry(f'{name}_SAL', type_, source, time_header, header_index)
            d = self._combine_entry(d, d1)
            header_index += 1
        if self.include_temperature:
            d1 = self._create_entry(f'{name}_TEMP', type_, source, time_header, header_index)
            d = self._combine_entry(d, d1)
            header_index += 1
        for i in range(self.nsed):
            d1 = self._create_entry(f'{name}_SED{i+1}', type_, source, time_header, header_index)
            d = self._combine_entry(d, d1)
            header_index += 1
        for i in range(self.ntracer):
            d1 = self._create_entry(f'{name}_TRACE{i+1}', type_, source, time_header, header_index)
            d = self._combine_entry(d, d1)
            header_index += 1
        for wq_const in self.wq_constituents:
            d1 = self._create_entry(f'{name}_{wq_const}', type_, source, time_header, header_index)
            d = self._combine_entry(d, d1)
        
        return d


class _WL(_BC):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['WL']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'WL'
    
    def is_modifier(self) -> bool:
        return self.has_sub_type() and self.sub_type() == 5
    
    def add_modifier(self, bc_mod: _BC):
        if not isinstance(bc_mod, _WL) or bc_mod.boundary_type_name() != self.boundary_type_name():
            logger.warning(f'{bc_mod} should be a {self.boundary_type_name()} type, not a {bc_mod.boundary_type_name()}')
            return
        self.modifiers.append(bc_mod)

    def apply_modifier(self, orig_val: pd.DataFrame | float, mod_val: pd.DataFrame | float):
        if self.sub_type() != 5:
            logger.warning(f'Unrecognised or unsupported boundary modifier sub_type for {self.id}: {self.sub_type()}')
            return
        
        # sub_type = 5, adds to the existing boundary
        if not isinstance(orig_val, (float, pd.DataFrame)):
            return orig_val
        
        if isinstance(orig_val, float):
            return orig_val + mod_val
        
        df = mod_val.reindex(mod_val.index.union(orig_val.index)).interpolate("index").loc[orig_val.index]
        if len(df.columns) != len(orig_val.columns):
            logger.warning(f'Number of columns in modifier data ({len(df.columns)}) does not match the original boundary data ({len(orig_val.columns)})')
            return orig_val
        df.columns = orig_val.columns
        return orig_val + df       
    

class _WLS(_WL):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        # WLS does not support temp, sal, sed, tracer, wq
        super().__init__(parent, control, False, False, 0, 0, [])

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['WL_A', 'WL_B']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'WLS'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:]
    

class _WLCurtain(_WLS):

    @staticmethod
    def supports_value_extraction() -> bool:
        return False

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['Chainage', 'ZTYPE', 'WL']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'WL_CURT'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[1:3]
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[2]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=3)
    

class _Q(_BC):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['Q']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'Q'
    

class _QC(_Q):
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'QC'
    

class _QCPoly(_Q):
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'QC_POLY'
    

class _QCGrid(_BC):

    @staticmethod
    def supports_value_extraction() -> bool:
        return False

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['Weight', 'Q']

    @staticmethod
    def boundary_type_name() -> str:
        return 'QC_GRID'
    
    def additional_column_names(self) -> list[str]:
        return ['weight']
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[2]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=2)
    

class _QCM(_Q):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.parent:
            self.parent.qcm_count += 1
        self.id = f'QCM_{self.parent.qcm_count}' if self.parent else 'QCM'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['X', 'Y', 'Q']

    @staticmethod
    def boundary_type_name() -> str:
        return 'QCM'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[1:3]
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=3)
    

class _QG(_Q):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = 'QG'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['Q/A']

    @staticmethod
    def boundary_type_name() -> str:
        return 'QG'
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)


class _HQ(_BC):

    @staticmethod
    def is_temporal() -> bool:
        return False

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['H', 'Q']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'HQ'
    
    def default_column_names(self) -> list[str]:
        col_names = super().default_column_names()
        col_names.pop(0)  # Remote "Time" column
        return col_names
    

class _QN(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        # QN does not support temp, sal, sed, tracer, wq
        super().__init__(parent, control, False, False, 0, 0, [])
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        self.bc_header = [rhs[2]]
        self.bc_scale = ['']
        self.bc_offset = ['']
        self.bc_default = ['']

    @staticmethod
    def is_temporal() -> bool:
        return False

    @staticmethod
    def boundary_type_name() -> str:
        return 'QN'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []
    
    def default_column_names(self) -> list[str]:
        return []
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        value = rhs[2]
        source = ''
        time_header = ''

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=0)
    

class _W10(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.id = 'W10'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['W10_X', 'W10_Y']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'W10'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:]

    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _Precip(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, include_temperature, 0, 0, [])
        self.id = 'PRECIP'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['PRECIP']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'PRECIP'
    
    def default_column_names(self) -> list[str]:
        names = ['TIME'] + self.default_bc_column_names()
        if self.include_temperature:
            names.append('PRECIP_TEMP')
        return names
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _AtmosGrid(_Precip):
    """Not a BC type. This is a base class for ATMOS GRIDS"""

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        self.id = f'{rhs[1]}_{self.name()}'

    @staticmethod
    def supports_value_extraction() -> bool:
        return False
    
    @staticmethod
    def boundary_type_name() -> str:
        raise NotImplementedError
    
    @staticmethod
    def name() -> str:
        return ''
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[2]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _PrecipGrid(_AtmosGrid):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, include_temperature, 0, 0, [])

    @staticmethod
    def supports_value_extraction() -> bool:
        return False

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['PRECIP']
    
    @staticmethod
    def name() -> str:
        return 'PRECIP'

    @staticmethod
    def boundary_type_name() -> str:
        return 'PRECIP_GRID'
    

class _W10Grid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['W10_X', 'W10_Y']
    
    @staticmethod
    def name() -> str:
        return 'W10'

    @staticmethod
    def boundary_type_name() -> str:
        return 'W10_GRID'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:]
    

class _MSLPGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['MSLP']
    
    @staticmethod
    def name() -> str:
        return 'MSLP'

    @staticmethod
    def boundary_type_name() -> str:
        return 'MSLP_GRID'
    

class _AirTempGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['AIR_TEMP']
    
    @staticmethod
    def name() -> str:
        return 'AIR_TEMP'

    @staticmethod
    def boundary_type_name() -> str:
        return 'AIR_TEMP_GRID'
    

class _CloudGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['CLOUD']
    
    @staticmethod
    def name() -> str:
        return 'CLOUD'

    @staticmethod
    def boundary_type_name() -> str:
        return 'CLOUD_GRID'
    

class _LWRadGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['LW_RAD']
    
    @staticmethod
    def name() -> str:
        return 'LW_RAD'

    @staticmethod
    def boundary_type_name() -> str:
        return 'LW_RAD_GRID'
    

class _SWRadGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['SW_RAD']
    
    @staticmethod
    def name() -> str:
        return 'SW_RAD'

    @staticmethod
    def boundary_type_name() -> str:
        return 'SW_RAD_GRID'
    

class _RelHumGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['REL_HUM']
    
    @staticmethod
    def name() -> str:
        return 'REL_HUM'

    @staticmethod
    def boundary_type_name() -> str:
        return 'REL_HUM_GRID'
    

class _LWNetGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['LW_NET']
    
    @staticmethod
    def name() -> str:
        return 'LW_NET'

    @staticmethod
    def boundary_type_name() -> str:
        return 'LW_NET_GRID'
    

class _SurfTempGrid(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['SURF_TEMP']
    
    @staticmethod
    def name() -> str:
        return 'SURF_TEMP'

    @staticmethod
    def boundary_type_name() -> str:
        return 'SURF_TEMP_GRID'
    

class _OBCGrid(_AtmosGrid):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, include_salinity, include_temperature, 0, 0, [])

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['SSH', 'U', 'V']
    
    @staticmethod
    def name() -> str:
        return 'SURF_TEMP'

    @staticmethod
    def boundary_type_name() -> str:
        return 'SURF_TEMP_GRID'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:4]
    

class _Wave(_AtmosGrid):

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['HSIGN','TPS','DIR','UBOT','TMBOT','FORCE_X','FORCE_Y','DEPTH']
    
    @staticmethod
    def name() -> str:
        return 'WAVE'

    @staticmethod
    def boundary_type_name() -> str:
        return 'WAVE'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:]
    

class _CycHolland(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.id = 'CYC_HOLLAND'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['X','Y','P0','PA','RMAX','B','RHOA','KM', 'THETMAX', 'DELTAFM', 'WBGX', 'WBGY']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'CYC_HOLLAND'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[2:]
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _WaveCoupled(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.bc_header = ['', '']
        self.bc_scale = ['']
        self.bc_offset = ['']
        self.bc_default = ['']
        self.id = 'WAVE_COUPLED'

    @staticmethod
    def supports_value_extraction() -> bool:
        return False

    @staticmethod
    def boundary_type_name() -> str:
        return 'WAVE_COUPLED'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _Force(_W10):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        self.id = rhs[1] if len(rhs) > 0 else ''

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['FORCEX', 'FORCEY']
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'FORCE'
    
    def bc_dbase_entry(self) -> dict:
        return _BC.bc_dbase_entry(self)
    

class _ForcePoly(_Force):

    @staticmethod
    def boundary_type_name() -> str:
        return 'FORCE_POLY'
    

class _ForceM(_Force):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.parent:
            self.parent.forcem_count += 1
        self.id = f'FORCEM_{self.parent.forcem_count}' if self.parent else 'FORCEM'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['X', 'Y', 'FORCEX', 'FORCEY']

    @staticmethod
    def boundary_type_name() -> str:
        return 'FORCEM'
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[1:4]
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        if self.parent:
            self.parent.forcem_count += 1
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=4)
    

class _ZG(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.bc_header = ['', '']
        self.bc_scale = ['']
        self.bc_offset = ['']
        self.bc_default = ['']

    @staticmethod
    def supports_value_extraction() -> bool:
        return False
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []

    @staticmethod
    def boundary_type_name() -> str:
        return 'ZG'
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        type_ = rhs[0]
        name = self.id
        source = ''
        time_header = ''

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _RS(_ZG):

    @staticmethod
    def boundary_type_name() -> str:
        return 'RS'
    

class _RNS(_ZG):

    @staticmethod
    def boundary_type_name() -> str:
        return 'RNS'
    

class _Atmos(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.id = self.boundary_type_name()

    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _AirTemp(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'AIR_TEMP'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['AIR_TEMP']
    

class _Cloud(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'CLOUD'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['CLOUD']


class _LWNet(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'LW_NET'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['LW_NET']
    

class _LWRad(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'LW_RAD'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['LW_RAD']
    

class _SWRad(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'SW_RAD'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['SW_RAD']
    

class _RelHum(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'REL_HUM'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['REL_HUM']
    

class _Snow(_Atmos):

    @staticmethod
    def boundary_type_name() -> str:
        return 'SNOW'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['SNOW']
    

class _FC(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        if not include_salinity and not include_temperature and ntracer < 1 and nsed < 1 and not wq_constituents:
            raise ValueError('Mass flux boundary requires a constituent')
        super().__init__(parent, control, include_salinity, include_temperature, nsed, ntracer, wq_constituents)
        self.include_primary = False

    @staticmethod
    def boundary_type_name() -> str:
        return 'FC'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []
    
    def default_column_names(self) -> list[str]:
        """Returns a complete list of the default column names, including columns for salinity, temp, sed, tracer, and wq."""
        names = ['TIME'] + self.default_bc_column_names()
        if self.include_salinity:
            names.append('FLUX_SAL')
        if self.include_temperature:
            names.append('FLUX_HEAT')
        for n in range(self.nsed):
            names.append(f'FLUX_SED_{n+1}')
        for n in range(self.ntracer):
            names.append(f'FLUX_TRACE_{n+1}')
        for n in range(self.nwq):
            names.append(f'FLUX_WQ_{n+1}')
        return names
    

class _FCPoly(_FC):

    @staticmethod
    def boundary_type_name() -> str:
        return 'FC_POLY'
    

class _FCM(_FC):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.parent:
            self.parent.fcm_count += 1
        self.id = f'FCM_{self.parent.fcm_count}' if self.parent else 'FCM'

    @staticmethod
    def boundary_type_name() -> str:
        return 'FCM'

    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['X', 'Y']
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[1:3]
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=3)
    

class _FCGrid(_FC):

    @staticmethod
    def supports_value_extraction() -> bool:
        return False
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'FC_GRID'
    

class _FB(_FC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, nsed, 0, [])

    @staticmethod
    def boundary_type_name() -> str:
        return 'FB'
    

class _FBPoly(_FB):

    @staticmethod
    def boundary_type_name() -> str:
        return 'FB_POLY'
    

class _FBM(_FB):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.parent:
            self.parent.fbm_count += 1
        self.id = f'FBM_{self.parent.fbm_count}' if self.parent else 'FBM'

    @staticmethod
    def boundary_type_name() -> str:
        return 'FBM'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return ['X', 'Y']
    
    def additional_column_names(self) -> list[str]:
        return self.bc_header[1:3]
    
    @staticmethod
    def additional_columns_come_after() -> bool:
        return False
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=3)
    

class _Scalar(_BC):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.include_primary = False

    @staticmethod
    def boundary_type_name() -> str:
        return 'SCALAR'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 3:
            logger.error(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 3 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = rhs[1]
        type_ = rhs[0]
        source = rhs[2]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)
    

class _CP(_Scalar):

    @staticmethod
    def is_temporal() -> bool:
        return False
    
    @staticmethod
    def boundary_type_name() -> str:
        return 'CP'
    

class _CPPoly(_CP):

    @staticmethod
    def boundary_type_name() -> str:
        return 'CP_POLY'
    

class _Transport(_BC):

    def __init__(self, parent: 'VirtualFVBCDatabase', control: 'BCBlockControl', include_salinity: bool, include_temperature: bool, nsed: int, ntracer: int, wq_constituents: list[str]):
        super().__init__(parent, control, False, False, 0, 0, [])
        self.id = 'TRANSPORT'
        self.bc_header = ['', '']
        self.bc_scale = ['']
        self.bc_offset = ['']
        self.bc_default = ['']

    @staticmethod
    def supports_value_extraction() -> bool:
        return False

    @staticmethod
    def boundary_type_name() -> str:
        return 'TRANSPORT'
    
    @staticmethod
    def default_bc_column_names() -> list[str]:
        return []
    
    def bc_dbase_entry(self) -> dict:
        if len(self.parent_input.value) != 2:
            logger.error(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command, but got %d: %s', len(self.parent_input.value), self.parent_input.value)
            raise ValueError(f'Expected 2 values for a "{self.boundary_type_name()} BC" block command')
        
        rhs = [x.strip() for x in self.parent_input.rhs.split(',')]
        name = self.id
        type_ = rhs[0]
        source = rhs[1]
        time_header = self.bc_header[0]

        return self._bc_dbase_entry(name, type_, source, time_header, start_header_index=1)


_bc_class_list = {}
def _populate_bc_classes():
    for _, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj) and issubclass(obj, _BC):
            try:
                _bc_class_list[obj.boundary_type_name().upper()] = obj
            except NotImplementedError:
                pass


def _get_bc_class(type_: str) -> type[_BC]:
    if not _bc_class_list:
        _populate_bc_classes()
    cls = _bc_class_list.get(type_.upper())
    if cls:
        return cls
    logger.error('Unsupported BC block type: %s', type_)
    raise KeyError(f'Unsupported BC block type: {type_}')


class FVBCDatabaseMixin:
    """Functions that are shared between the build and runstate and can be added
    to both via a mixin.
    """

    @property
    def fvc(self) -> 'FVCBase | None':
        if self.parent:
            return self.parent.fvc

    def is_piecewise_constant(self, item: str | int) -> bool:
        """Returns whether the returned temporal data from the boudary should be treated as piecewise constant.
        
        This essentially returns whether a given boundary has an update dt interval that is not zero.

        Parameters
        ----------
        item : str | int
            The item name or index in the database.
        
        Returns
        -------
        bool
            True if the item is piecewise constant, False otherwise.
        """
        if hasattr(self, 'bs'):
            bc_class = self.bs.item2bc_class[item]
        else:
            bc_class = self.item2bc_class[item]
        return bc_class.is_temporal() and bc_class.bc_update_interval > 0.
    
    def create_dataframe(self, bc_classes: dict[str, _BC]):
        d = OrderedDict([
            ('Name', []),
            ('Type', []),
            ('Source', []),
            ('Column 1', []),
            ('Column 2', []),
            ('BC Scale', []),
            ('BC Offset', []),
            ('Default Value', []),
        ])
        for _, bc_class in bc_classes.items():
            entry = bc_class.bc_dbase_entry()
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
                            self.item2bc_class[n] = bc_class
                    else:
                        self.item2bc_class[v] = bc_class
                lst.extend(v) if isinstance(v, list) else lst.append(v)
                
        df = pd.DataFrame(d)
        self.df = df.set_index('Name')


class VirtualFVBCDatabase(BCDatabase, FVBCDatabaseMixin):
    """Virtual boundary condition database used to display and organise FV BC blocks."""
    SOURCE_INDEX = 2
    TIME_INDEX = 3
    VALUE_INDEX = 4
    TIME_ADD_INDEX = -1
    VALUE_FACTOR_INDEX = 5
    VALUE_ADD_INDEX = 6
    DEFAULT_INDEX = 7
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fpath = self.parent.fpath if self.parent else None
        self.item2bc_class = CaseInsDictOrdered()  # mapping database index to the bc block control class
        self.qcm_count = 0
        self.forcem_count = 0
        self.fcm_count = 0
        self.fbm_count = 0

    def __repr__(self):
        if self.parent:
            return '<{0}> ({1})'.format(self.__class__.__name__, self.parent.fpath.name)
        return '<{0}>'.format(self.__class__.__name__)
    
    @property
    def df(self) -> pd.DataFrame:
        return BCDatabase.df.fget(self)

    @df.setter
    def df(self, value: pd.DataFrame):
        self._df = value
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=value.copy())
    
    @staticmethod
    def from_bc_controls(fvc: 'FVCBase', controls: list['BCBlockControl']) -> 'VirtualFVBCDatabase':
        """Creates a VirtualFVBCDatabase from a list of BCBlockControls."""
        bc_dbase = VirtualFVBCDatabase(config=fvc.config, parent=fvc)

        bc_classes = {}
        bc_modifiers = []
        for bc_control in controls:
            try:
                bc_cls = _get_bc_class(bc_control.parent_input.value[0])
                bc = bc_cls(
                    bc_dbase,
                    bc_control, 
                    fvc.include_salinity(), 
                    fvc.include_temperature(), 
                    fvc.sediment_fraction_count() if fvc.include_sediment() else 0,
                    fvc.tracer_count(),
                    fvc.wq_constituents()
                )
                if bc.is_modifier():
                    bc_modifiers.append(bc)
                    continue
                counter = 1
                while bc.id in bc_classes:  # ensure id is unique
                    bc.id = f'{bc.id}_{counter}' if counter == 1 else '{0}_{1}'.format('_'.join(bc.id.split('_')[:-1]), counter)
                    counter += 1
                bc_classes[bc.id] = bc
            except (ValueError, KeyError):
                pass
            except Exception as e:
                logger.error('Unexpected error (%s) processing BC block control input: %s', bc_control, str(e))

        for bc_mod in bc_modifiers:
            bc = bc_classes.get(bc_mod.id)
            if bc is None:
                logger.warning(f'{bc_mod.id} is a modifier, but cannot find the boundary to modify')
                continue
            try:
                bc.add_modifier(bc_mod)
            except NotImplementedError:
                logger.warning(f'{bc_mod.id} modifier has not been implemented yet')

        bc_dbase.create_dataframe(bc_classes)
        bc_dbase.reload()

        return bc_dbase

    def _load(self, fpath: Path):
        # override and do nothing
        pass

    def reload(self):
        self._load_from_df(self.df)
        self.loaded = True

    def entry_class(self) -> type[FVBCDatabaseEntry]:
        return FVBCDatabaseEntry

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'VirtualFVBCDatabaseRunState':
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return VirtualFVBCDatabaseRunState(self, ctx, parent)
    
    def value(self, item: str | int) -> typing.Any:
        bc_class = self.item2bc_class[item]
        if not bc_class.supports_value_extraction():
            raise NotImplementedError(f'Value extraction is not yet supported for BC type "{bc_class.boundary_type_name()}"')
        if not bc_class.resolved:
            raise ValueError('Requires context to resolve')
        return super().value(item)
    
    def is_plottable(self, item: str | int) -> bool:
        bc_class = self.item2bc_class[item]
        if not bc_class.supports_value_extraction():
            return False
        return super().is_plottable(item)


class VirtualFVBCDatabaseRunState(BCDatabaseRunState, FVBCDatabaseMixin):

    def __init__(self, *args, **kwargs):
        self.item2bc_class = CaseInsDictOrdered()  # mapping database index to the bc block control class
        self.qcm_count = 0
        self.forcem_count = 0
        self.fcm_count = 0
        self.fbm_count = 0
        super().__init__(*args, **kwargs)
        self.fpath = self.parent.fpath if self.parent else None

    @property
    def df(self):
        return self._df
    
    @df.setter
    def df(self, value: pd.DataFrame):
        self._df = value

    def _resolve_scope_in_context(self):
        super()._resolve_scope_in_context()

        fvc = self.fvc if self.fvc else self.bs.fvc
        if not fvc:
            logger.error('Should not be here - unable to get FVC parent control class')
            raise ValueError('Unable to get FVC parent control class')

        bc_classes = {}
        bc_modifiers = []
        for item in self.entries:
            orig = self.bs.item2bc_class[item]
            bc_control = orig.control
            if isinstance(bc_control, BuildState):
                bc_control_ctx = bc_control.context(context=self.ctx, parent=self.parent)
                bc_control_ctx.parent_input = bc_control.parent_input.context(context=self.ctx, parent=bc_control.parent)
            else:
                bc_control_ctx = bc_control
            try:
                bc_cls = _get_bc_class(bc_control.parent_input.value[0])
                bc = bc_cls(
                    self,
                    bc_control_ctx, 
                    fvc.include_salinity(), 
                    fvc.include_temperature(), 
                    fvc.sediment_fraction_count() if fvc.include_sediment() else 0,
                    fvc.tracer_count(),
                    fvc.wq_constituents()
                )
                bc.id = orig.id
                bc.modifiers = orig.modifiers.copy()
                bc_classes[orig.id] = bc
            except (ValueError, KeyError):
                pass
            except Exception as e:
                logger.error('Unexpected error (%s) processing BC block control input: %s', bc_control, str(e))
        
        self.create_dataframe(bc_classes)
        for index, row in self.df.iterrows():
            self.entries[index] = self.bs.entry_class()(index, row.tolist(), self.config, self)

    def is_plottable(self, item: str | int) -> bool:
        bc_class = self.item2bc_class[item]
        if not bc_class.supports_value_extraction():
            return False
        return super().is_plottable(item)

    def value(self, item: str | int):
        df_add = None
        entry = self[item]
        bc_class = self.item2bc_class[item]
        default = entry[self.bs.DEFAULT_INDEX].value
        try:
            default = float(default)
        except (ValueError, TypeError):
            pass
        
        # base bc_dbase.value() supports one value column only - we might need to extract more columns for some FV data
        if entry.uses_source_file and bc_class.additional_column_names():
            col_labels = bc_class.additional_column_names()

            # make sure to resolve columns names, they could be using variables
            for i, label in enumerate(col_labels[:]):
                col_labels[i] = self.ctx.translate(label)

            search_labels = [entry[self.bs.TIME_INDEX].value]
            source = entry[self.bs.SOURCE_INDEX].value_expanded_path
            source_df = self._load_source_as_df(source, search_labels)

            # sort out which columns are actually present and make case align with what is actually there
            col_labels_present = []
            col_labels_missing = []
            for i, label in enumerate(col_labels):
                if label.lower() in source_df.columns.str.lower():
                    label_case_sensitive = source_df.columns[source_df.columns.str.lower().get_loc(label.lower())]
                    col_labels_present.append(label_case_sensitive)
                    col_labels[i] = label_case_sensitive
                else:
                    col_labels_missing.append(label)
            df_add = source_df[col_labels_present]
            for label in col_labels_missing:
                df_add[label] = default
            df_add = df_add[col_labels]

        df = super().value(item)
        if not isinstance(df, pd.DataFrame):
            return df
        
        if pd.api.types.is_string_dtype(df.index):
            test = str(df.index[0])
            format = '%d/%m/%Y %H:%M'
            if re.match(r'^\d{2}/\d{2}/\d{4}\s\d{2}:\d{2}:\d{2}$', test):
                format = '%d/%m/%Y %H:%M:%S'
            try:
                df.index = pd.to_datetime(df.index, format=format)
            except ValueError:
                pass
        
        # if the column did not exist in the CSV, use default value for entire column
        if df.shape[1] == 0 and self.bs.DEFAULT_INDEX > -1:
            val_col = entry[self.bs.VALUE_INDEX].value
            df[val_col] = default
            return df
        
        # if the default value is not nan, replace nan with default value
        if self.bs.DEFAULT_INDEX > -1:
            if not np.isnan(default):
                val_col = df.columns[0]
                df.loc[:,df[val_col].isna()] = default

        # add any additional columns here
        if df_add is not None:
            ordered_cols = df.columns.tolist() + col_labels if bc_class.additional_columns_come_after() else col_labels + df.columns.tolist()
            df[col_labels] = df_add[col_labels].to_numpy()
            df = df[ordered_cols]

        # adjust dt
        if bc_class.bc_update_interval > 0. and bc_class.is_temporal():
            if isinstance(df.index, pd.DatetimeIndex):
                update_interval = pd.Timedelta(seconds=bc_class.bc_update_interval)
                new_index = pd.date_range(df.index[0], df.index[-1] + update_interval, freq=update_interval, name=df.index.name)
                if (new_index[-1] - df.index[-1]).seconds > 0.01:
                    new_index = new_index[:-1]
            else:
                update_interval = bc_class.bc_update_interval / 3600.  # convert to hours - bc_interval input is in seconds, time series is assumed to be hours
                for inp in bc_class.control.find_input(lhs='bc time units'):
                    if isinstance(inp.value, str) and inp.value.upper() == 'DAYS':
                        update_interval = bc_class.bc_update_interval / 3600. / 24.
                    elif isinstance(inp.value, str) and inp.value.upper() == 'MINUTES':
                        update_interval = bc_class.bc_update_interval / 60.
                    elif isinstance(inp.value, str) and inp.value.upper() == 'SECONDS':
                        update_interval = bc_class.bc_update_interval
                
                new_index = np.arange(df.index[0], df.index[-1] + update_interval, update_interval)
                if new_index[-1] - df.index[-1] > 0.001:
                    new_index = new_index[:-1]

            df = df.reindex(df.index.union(new_index)).interpolate("index").loc[new_index]

        # add any modifiers
        for mod in bc_class.modifiers:
            # extract value - easiest way is to create a temporary bc_dbase and extract the value
            bc_dbase = bc_dbase = VirtualFVBCDatabase(config=self.config, parent=self.parent)
            bc_dbase.create_dataframe({mod.id: mod})
            bc_dbase.reload()
            bc_dbase_ctx = bc_dbase.context(context=self.ctx, parent=self.parent)
            mod_df = bc_dbase_ctx.value(mod.id)

            # apply modifier
            df = mod.apply_modifier(df, mod_df)
        
        return df
