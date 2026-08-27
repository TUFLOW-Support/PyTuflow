import logging

from .cf_load_factory import ControlFileLoadMixin
from .fv_build_state import FVControlFileBuildState
from .cf_run_state import ControlFileRunState
from ..context import Context
from ..parsers.fvcommand import Command, FVWaterQualityCommand
from .. import const


logger = logging.getLogger('pytuflow')


class FVWQMixin:

    def simulation_class(self) -> str:
        """Returns the simulation class being used. If the simulation class command is within
        a IF Scenario/Event block, then the most complex class is returned i.e. preference will
        be given to "Organics", "Inorganics", "DO" in that order.
        
        Returns
        -------
        str : 
            The simulation class being used. If no simulation class is found, "NONE" is returned.
        """
        sim_class = 'DO'
        for inp in self.find_input(lhs='simulation class'):
            if isinstance(inp.value, str) and inp.value.upper() == 'ORGANICS':
                sim_class = 'ORGANICS'
                break
            elif isinstance(inp.value, (list, tuple)) and isinstance(inp.value[0], str) and inp.value[0].upper() == 'ORGANICS':
                sim_class = 'ORGANICS'
                break
            elif isinstance(inp.value, str) and inp.value.upper() == 'INORGANICS':
                sim_class = 'INORGANICS'
            elif isinstance(inp.value, (list, tuple)) and isinstance(inp.value[0], str) and inp.value[0].upper() == 'INORGANICS':
                sim_class = 'INORGANICS'
        return sim_class
    
    def phosphorus_model(self) -> str:
        """Returns the phosphorus model. If the simulation class command is within a IF Scenario/Event
        block, the FRPhsAds is preferenced.
        
        Returns
        -------
        str : 
            The phosphorus model being used. If no phosphorus model is found, "FRP" is returned unless the simulation
            class is DO, then "NONE" is returned.
        """
        phos_model = 'NONE'
        if self.simulation_class() == 'DO':
            return phos_model
        phos_model = 'FRPHS'
        for inp in self.find_input(lhs='phosphorus model'):
            if isinstance(inp.value, str) and inp.value.upper() == 'FRPHSADS':
                return inp.value.upper()
            elif isinstance(inp.value, (list, tuple)) and isinstance(inp.value[0], str) and inp.value[0].upper() == 'FRPHSADS':
                return inp.value[0].upper()
        return phos_model
    
    def organic_matter_model(self) -> str:
        """Returns the organics matter model. If the command is within a IF Scenario/Event block, the
        "REFRACTORY" is preferenced.

        Returns
        -------
        str : 
            The organics matter model being used. If no organics matter model is found, "LABILE" is returned unless
            the simulation class is not ORGANICS, then "NONE" is returned. 
        """
        model = 'NONE'
        if self.simulation_class() != 'ORGANICS':
            return model
        model = 'LABILE'
        for inp in self.find_input(lhs='organic matter model'):
            if isinstance(inp.value, str) and inp.value.upper() == 'REFRACTORY':
                return inp.value.upper()
            elif isinstance(inp.value, (list, tuple)) and isinstance(inp.value[0], str) and inp.value[0].upper() == 'REFRACTORY':
                return inp.value[0].upper()
        return model

    def wq_constituents(self) -> list[str]:
        """Returns a list of water quality constiutents present in the model.

        Returns
        -------
        list[str] : 
            A list of water quality constituents. If no water quality constituents are found, an empty list is returned.
        """
        # pathogens and phytoplankten are already added at end of returned list (order: phyto, pathogen)
        def add_pathogens(wq_const):
            for pathogen_name, pathogen_model in self.pathogens().items():
                pathogen_name = f'PATH_{pathogen_name}'
                wq_constituents.append(f'{pathogen_name}_ALIVE')
                if pathogen_model.lower() == 'attached':
                    wq_constituents.append(f'{pathogen_name}_ATTACHED')
                wq_constituents.append(f'{pathogen_name}_DEAD')

        def add_phytos(wq_const):
            for phyto_name, phyto_model in self.phytos().items():
                phyto_name1 = f'PHYTO_{phyto_name}'
                wq_const.append(phyto_name1)
                if self._phyto_uses_stokes_settling(phyto_name):
                    wq_const.append(f'{phyto_name1}_DENSITY')
                if phyto_model.lower() == 'advanced':
                    wq_const.append(f'{phyto_name1}_IN')
                    wq_const.append(f'{phyto_name1}_IP')

        sim_class = self.simulation_class()

        # initialise with DO, this is always there
        wq_constituents = ['DO']
        
        if sim_class == 'DO':
            add_pathogens(wq_constituents)
            return wq_constituents
        
        wq_constituents.append('Si')
        wq_constituents.append('Amm')
        wq_constituents.append('Nit')
        wq_constituents.append('FRP')
        if self.phosphorus_model() == 'FRPHSADS':
            wq_constituents.append('FRPads')

        if sim_class == 'INORGANICS':
            add_phytos(wq_constituents)
            add_pathogens(wq_constituents)
            return wq_constituents
        
        wq_constituents.extend([
            'DOC', 'POC', 'DON', 'PON', 'DOP', 'POP'
        ])
        if self.organic_matter_model() == 'REFRACTORY':
            wq_constituents.extend([
                'RDOC', 'RDON', 'RDOP', 'RPOM'
            ])
        
        add_phytos(wq_constituents)
        add_pathogens(wq_constituents)

        return wq_constituents
    
    def pathogens(self) -> dict[str, str]:
        """Returns the pathogens as (name, model) pairs.
        
        Returns
        -------
        dict[str, str] : 
            A dictionary of pathogen names and their corresponding model. If no pathogens are found, an empty dictionary is returned.
        """
        return self._group_names(lhs='pathogen model')
    
    def phytos(self) -> dict[str, str]:
        """Returns the phytoplankten as (name, model) pairs.
        
        Returns
        -------
        dict[str, str] : 
            A dictionary of phytoplankten names and their corresponding model. If no phytoplankten are found, an empty dictionary is returned.
        """
        return self._group_names(lhs='phyto model')
    
    def _phyto_uses_stokes_settling(self, phyto_name: str) -> bool:
        found = False
        for inp in self.find_input(lhs='phyto model', rhs=phyto_name):
            found = True
            for cf in inp.cf:
                if cf.find_input(lhs='settling', rhs='stokes'):
                    return True
        if not found:
            logger.warning(f'Phyto block was not found: {phyto_name}')
        return False
    
    def _command_class(self) -> type[Command]:
        return FVWaterQualityCommand


class FVWQ(ControlFileLoadMixin, FVControlFileBuildState, FVWQMixin):
    """Initialises the FV Water Quality Control File class in a build state.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the FVWQ will be initialised as an
        empty control file.

    **kwargs : optional parameters

        - config : FVCConfig, optional
            This object stores useful information such as variable mappings, the event database,
            current spatial database etc. If set to None, a new FVCConfig object will be created.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a TGC, the parent
            should be set to the FVC.
        - scope : ScopeList, optional
            A list of scope objects that will be inherited by the control file itself. Not currently used
            but reserved in case this is useful information in the future.
        - log_level : str, optional
            The logging level to use for the control file. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'WARNING'.
        - log_to_file : PathLike, optional
            If set, will log the control file to the given file path. Default is None.
    """
    TUFLOW_TYPE = const.CONTROLFILE.FVWQ
    pass

    def context(self,
                    run_context: str | dict[str, str] = '',
                    context: Context | None = None,
                    parent: ControlFileRunState | None = None) -> 'FVWQRunState':
            # docstring inherited
            ctx = context if context else Context(run_context, config=self.config)
            return FVWQRunState(self, ctx, parent)


class FVWQRunState(ControlFileRunState, FVWQMixin):
    pass
