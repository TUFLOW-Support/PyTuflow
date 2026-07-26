from __future__ import annotations

import re
from pathlib import Path

from .._common.project import BaseEngineProject
from .._common.utils import _variables_from_cf_path  # noqa: F401 — kept for back-compat

# Maps CF type key → TCF command lhs that references it, and the pytuflow class to use.
_CF_TYPE_MAP: dict[str, dict] = {
    'tgc': {'lhs': 'geometry control file', 'class': 'TGC'},
    'tbc': {'lhs': 'bc control file', 'class': 'TBC'},
    'ecf': {'lhs': 'estry control file', 'class': 'ECF'},
    'qcf': {'lhs': 'quadtree control file', 'class': 'QCF'},
    'adcf': {'lhs': 'ad control file', 'class': 'ADCF'},
}


def get_available_modules() -> dict[str, type]:
    """Discover all available HPC modules from JSON files in the module cache.

    Returns a dict mapping module name → dynamically-created subclass of
    :class:`HPCBaseModule`.  Adding a new module requires only a JSON file
    in ``data/modules/hpc/`` — no Python code changes needed.
    """
    return HPCProject.get_available_modules()


_BASE_TEMPLATES = [
    ('runs/${model_name}_${iter}.tcf', 'runs/${model_name}_${iter}.tcf'),
    ('model/${model_name}_${iter}.tgc', 'model/${model_name}_${iter}.tgc'),
    ('model/${model_name}_${iter}.tbc', 'model/${model_name}_${iter}.tbc'),
    ('bc_dbase/bc_dbase.csv', 'bc_dbase/bc_dbase.csv'),
    ('model/${model_name}_mat.csv', 'model/${model_name}_mat.csv'),
]


class HPCProject(BaseEngineProject):
    r"""HPC project generator.

    The HPC project generator is a highly customisable class for generating
    an Classic/HPC project from scratch. The class uses template files, modules, variables,
    and directives, which are fully customisable and extendable by the user.

    When an HPC project is created for the first time, the template files are copied
    locally the users home directory, ``%userprofile%\.tuflow_model_files\project_templates``
    on Windows or ``~/.tuflow_model_files/project_templates`` on Linux. Subsequent calls
    will use these cached templates, and the user is free to modify and/or extend them.
    
    Parameters
    ----------
    name : str
        The name to be used for the project/model.
    output_dir : str | Path
        The directory to generate the project within.
    modules : list[str] | None, optional
        The modules to include within the generated project. The available modules are
        dynamic and can be modified or extended by the user. See the example section below
        to check the available modules. Modules can also be added post project generation using
        :meth:`pytuflow.HPCProject.insert_module_into<HPCProject.insert_module_into>`.
    crs : str
        The CRS to use for the project in the form of "AUTHORITY:CODE". E.g. the TUFLOW tutorial model
        would be ``"EPSG:32760"``
    create_empties : bool, optional
        Sets whether to generate empty files.
    **kwargs
        Sets any number of variables used in the template files. The 


    Examples
    --------
    List the available modules:

    >>> from pytuflow import HPCProject
    >>> for mod in HPCProject.get_available_modules():
    ...     print(mod)
    ad
    estry
    events
    po
    quadtree
    rf
    sgs
    soils
    toc
    tutorial
    """

    ENGINE_TYPE = 'hpc'
    MAIN_CF_EXT = 'tcf'
    MAIN_CF_CLASS = 'TCF'
    BASE_TEMPLATES = _BASE_TEMPLATES
    OUTPUT_DIRS = ['runs', 'model', 'bc_dbase', 'results', 'check', 'runs/log']
    EMPTIES_KEY = 'hpc'
    SUPPORTED_GIS_FORMATS = frozenset({'SHP', 'MIF', 'GPKG'})

    @classmethod
    def _get_module_base_class(cls):
        from .modules._base import HPCBaseModule
        return HPCBaseModule

    # ------------------------------------------------------------------
    # Secondary CF loading (HPC-specific — TGC, TBC, ECF, QCF, ADCF)
    # ------------------------------------------------------------------

    def _load_secondary_cfs(self, main_cf, main_cf_path: Path, modules) -> dict:
        needed = _needed_cf_types(modules)
        return _load_secondary_cfs(main_cf, main_cf_path, needed)

    @classmethod
    def _load_secondary_cfs_cls(cls, main_cf, main_cf_path: Path, modules) -> dict:
        needed = _needed_cf_types(modules)
        return _load_secondary_cfs(main_cf, main_cf_path, needed)


def _needed_cf_types(modules) -> set[str]:
    """Collect all non-primary target_cf values across all modules' command blocks."""
    needed = set()
    for module in modules:
        config = module._get_config()
        for block in config.get('command_blocks', []):
            target = block.get('target_cf', 'tcf')
            if target != 'tcf':
                needed.add(target)
    return needed


def _load_secondary_cfs(tcf, tcf_path: Path, needed_types: set[str]) -> dict:
    """Load secondary CFs (TGC, TBC, etc.) referenced in the TCF."""
    import pytuflow as pt

    cf_classes = {k: getattr(pt, v['class']) for k, v in _CF_TYPE_MAP.items()}
    result = {}
    for cf_type in needed_types:
        if cf_type not in _CF_TYPE_MAP:
            continue
        lhs = _CF_TYPE_MAP[cf_type]['lhs']
        inps = tcf.find_input(lhs=lhs, recursive=False)
        if not inps:
            continue
        cf_rel = str(inps[0].rhs).replace('\\', '/')
        cf_path = (tcf_path.parent / cf_rel).resolve()
        if cf_path.exists():
            result[cf_type] = cf_classes[cf_type](cf_path)
    return result


# Keep old name available for any code that imported it directly
_variables_from_tcf_path = _variables_from_cf_path
