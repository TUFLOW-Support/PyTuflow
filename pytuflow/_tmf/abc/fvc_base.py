import re
import logging
from collections import OrderedDict

from .. import const
from .cf import ControlFile
from .cf_universal_mixin import ControlFileUniversalMixin
from ..db.virtual_fv_bc_dbase import VirtualFVBCDatabase, VirtualFVBCDatabaseRunState
from ..db.virtual_fv_mat_dbase import VirtualFVMatDatabase, VirtualFVMatDatabaseRunState
from ..abc.t_cf import T_ControlFile
from ..scope import Scope
from ..abc.bld_state import BuildState


logger = logging.getLogger('pytuflow')


class FVBaseMixin:

    @property
    def fvc(self) -> 'FVCBase':
        if not self.parent:
            return self
        else:
            fvc = self.parent
            while fvc.parent:
                fvc = fvc.parent
            return fvc
        
    def _group_names(self, *args, **kwargs) -> dict[str, str]:
        """Returns the groups with the name as key, and type (if present) as the value."""
        groups = OrderedDict()  # use list not set to retain order
        groups_lower = {}
        for inp in self.find_input(*args, **kwargs):
            if not inp.value:
                continue
            if isinstance(inp.value, (list, tuple)):
                values = inp.value
            else:
                values = str(inp.value).split(',')
            key = values[-1]
            val = values[0] if len(values) > 1 else ''
            if key.lower() not in groups_lower:
                groups[key] = val
                groups_lower[key.lower()] = val
        return groups
    
    def _group_count(self, *args, **kwargs) -> int:
        return len(self._group_names(*args, **kwargs))



class FVCBase(ControlFile, FVBaseMixin, ControlFileUniversalMixin):

    def fvsed(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('sediment control file', **kwargs)
    
    def fvwq(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('water quality control file', **kwargs)
    
    def fvptm(self, *args, **kwargs) -> T_ControlFile:
        # doc deferred to subclasses
        return self._find_control_file('particle tracking control file', **kwargs)
    
    def bc_default_update_dt(self) -> float:
        """Returns the default BC Update dt interval.
        
        Returns
        -------
        float
            The update dt interval (s)

        Raises
        ------
        ValueError
            Raised if value requires a context to resolve i.e. the relevant command
            sits within an IF Scenario/Event block.
        """
        default_update_dt = 0.
        for inp in self.find_input(lhs='BC Default Update dt'):
            for scope in inp.scope:
                if scope in [Scope('Scenario'), Scope('Event'), Scope('EventVariable')]:
                    raise ValueError('BC Default Update dt requires a context to resolve.')
            try:
                default_update_dt = float(inp.value)
            except (ValueError, TypeError):
                default_update_dt = inp.value
            
        return default_update_dt
    
    def bc_dbase(self) -> VirtualFVBCDatabase | VirtualFVBCDatabaseRunState:
        """Generates a virtual boundary database file from the BC blocks.
        
        The returned database is read only.
        """
        bc_inputs = self.find_input(callback=lambda x: x.TUFLOW_TYPE == const.INPUT.BC_BLOCK)
        bc_controls = [input.block_control() for input in bc_inputs]
        bc_dbase = VirtualFVBCDatabase.from_bc_controls(self.fvc, bc_controls)
        if isinstance(self, BuildState):
            return bc_dbase
        else:
            return bc_dbase.context(context=self.ctx, parent=self)
        
    def mat_file(self) -> VirtualFVMatDatabase | VirtualFVMatDatabaseRunState:
        def is_non_default_mat_block(x):
            if x.TUFLOW_TYPE == const.INPUT.BLOCK and x.lhs.upper() == 'MATERIAL':
                if isinstance(x.value, str):
                    return x.value.lower() not in ['0', 'default']
                return x.value != 0
            return False
        mat_inputs = self.find_input(callback=is_non_default_mat_block)
        mat_controls = [input.block_control() for input in mat_inputs]
        mat_dbase = VirtualFVMatDatabase.from_mat_controls(self.fvc, mat_controls)
        if isinstance(self, BuildState):
            return mat_dbase
        else:
            return mat_dbase.context(context=self.ctx, parent=self)
    
    def include_salinity(self) -> bool:
        """Returns whether salinity is turned on. This method will return True if this setting
        is turned on anywhere in the model, regardless if the setting
        is turned on only within an If Scenario/Event block.

        Returns
        -------
        bool : 
            True if salinity is turned on anywhere in the model, False otherwise.
        """
        return self._is_setting_switched_on('include salinity')
    
    def include_temperature(self) -> bool:
        """Returns whether temperature is turned on. This method will return True if this setting
        is turned on anywhere in the model, regardless if the setting
        is turned on only within an If Scenario/Event block.

        Returns
        -------
        bool : 
            True if temperature is turned on anywhere in the model, False otherwise.
        """
        return self._is_setting_switched_on('include temperature')
    
    def include_sediment(self) -> bool:
        """Returns whether sediment is turned on. This method will return True if this setting
        is turned on anywhere in the model, regardless if the setting
        is turned on only within an If Scenario/Event block.

        Returns
        -------
        bool : 
            True if sediment is turned on anywhere in the model, False otherwise.
        """
        return self._is_setting_switched_on('include sediment')
    
    def is_3d(self) -> bool:
        """Returns whether the model is has 3D hydrodynamics enabled.
        
        Returns
        -------
        bool : 
            True if 3D hydrodynamics is enabled, False otherwise.
        """
        cmds = self.find_input(lhs='Vertical Mesh Type', recursive=False)
        return len(cmds) > 0
    
    def water_quality_model(self) -> str:
        """Returns the name of the water quality model being used. If the command sits within an If Scenario/Event block
        (and therefore multiple values could exist) the returned type will preference "TUFLOW", "EXTERNAL", "NONE" in that order.
        
        Returns
        -------
        str : 
            The water quality model being used. If no water quality model is found, "NONE" is returned.
        """
        wq_model = 'NONE'
        for inp in self.find_input(lhs='(?:water quality|wq) model', regex=True, regex_flags=re.IGNORECASE):
            if inp.value.upper() == 'TUFLOW':
                wq_model = 'TUFLOW'
                break
            elif inp.value.upper() == 'EXTERNAL':
                wq_model = 'EXTERNAL'
        return wq_model
    
    def sediment_fraction_count(self) -> int:
        """Returns the number of sediment groups.
        
        Returns
        -------
        int : 
            The number of sediment groups. If the number of sediment groups cannot be determined, then zero is returned.
        """
        return len(self.sediment_fractions())
        
    def sediment_fractions(self) -> list[str]:
        """Returns a unique list of the sediment fraction names.
        
        Returns
        -------
        list[str] : 
            A list of sediment fraction names. If no sediment groups are found, an empty list is returned.
        """
        fractions = []
        fractions_lower = []
        for inp in self.find_input(lhs='sediment control file'):
            for cf in inp.cf:
                for frac in cf.sediment_fractions():
                    if frac.lower() not in fractions_lower:
                        fractions.append(frac)
                        fractions_lower.append(frac.lower())
        return fractions
        
    def tracer_count(self) -> int:
        """Returns the number of tracers in the model.
        
        Returns
        -------
        int : 
            The number of tracers. If the number of tracers cannot be determined, then zero is returned.
        """
        count = 0
        for inp in self.find_input(lhs='ntracer', recursive=False):
            if isinstance(inp.value, (float, int)):
                count = max(count, int(inp.value))
            elif isinstance(inp.value, str):
                if re.match(r'^<<.*>>$', inp.value):
                    for inp2 in self.find_input(lhs=f'set variable {inp.value}'):
                        try:
                            count = max(count, int(inp2.value))
                        except ValueError:
                            pass
        count = max(count, self._group_count(lhs='^tracer$', regex=True, regex_flags=re.IGNORECASE))
        return count
    
    def wq_constituents(self) -> list[str]:
        """Returns a unique list of the water quality constituents in the model.
        
        Returns
        -------
        list[str] : 
            A list of water quality constituent names. If no constituents are found, an empty list is returned.
        """
        # check if water quality model is set to TUFLOW
        wq_model = self.water_quality_model()
        if wq_model == 'NONE':
            return []
        if wq_model == 'EXTERNAL':
            logger.warning('Model is using an external water quality model, unable to determine constituents.')
            return [] 

        wq_constituents = []
        wq_constituents_lower = []
        for inp in self.find_input(lhs='(?:water quality|wq) control file', regex=True, regex_flags=re.IGNORECASE):
            for cf in inp.cf:
                for constituent in cf.wq_constituents():
                    if constituent.lower() not in wq_constituents_lower:
                        wq_constituents.append(constituent)
                        wq_constituents_lower.append(constituent.lower())
        return wq_constituents

    def wq_constituent_count(self) -> int:
        """Returns the number of water quality constituents used in the model.
        
        Returns
        -------
        int : 
            The number of water quality constituents. If the number of constituents cannot be determined, then zero is returned.
        """ 
        return len(self.wq_constituents())
    
    def _is_setting_switched_on(self, setting_command: str) -> bool:
        """Determine if a given setting is turned on or not. The setting could be
        within a Scenario/Event block which means it cannot be determined. However,
        if the setting is turned on anywhere, then return True.
        """
        from ..scope import Scope
        for inp in self.find_input(lhs=setting_command):
            if inp.command().is_switched_on():
                return True
        return False
