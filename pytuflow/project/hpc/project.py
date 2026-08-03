from __future__ import annotations

import re
from pathlib import Path

from .._common.project import BaseEngineProject
from .._common.utils import _variables_from_cf_path  # noqa: F401 — kept for back-compat


def get_available_features() -> dict[str, type]:
    """Discover all available HPC features from JSON files in the feature cache.

    Returns a dict mapping feature name → dynamically-created subclass of
    :class:`HPCBasefeature`.  Adding a new feature requires only a JSON file
    in ``data/features/hpc/`` — no Python code changes needed.
    """
    return HPCProject.get_available_features()


class HPCProject(BaseEngineProject):
    r"""HPC project generator.

    The HPC project generator is a highly customisable class for generating
    a Classic/HPC project from scratch. The class uses template files, modular features, variables,
    and directives, which are fully customisable and extendable by the user.

    When an HPC project is created for the first time, the template files are copied
    locally to the users home directory:
    
    - Windows: ``%userprofile%\.tuflow_model_files\project_templates``
    - Linux: ``~/.tuflow_model_files/project_templates``
    
    Subsequent calls will use these cached templates, and the user is free to modify and/or extend them.

    Projects can also be created via the CLI with ``pytuflow-project create --engine hpc``.
    See below for examples.

    It is also possible to insert features into an existing project using 
    :meth:`HPCProject.insert_feature_into()<pytuflow.HPCProject.insert_feature_into>` or via the CLI
    with ``pytuflow-project insert --engine hpc``.
    
    Parameters
    ----------
    name : str
        The name to be used for the project/model.
    output_dir : str | Path
        The directory to generate the project within.
    features : list[str] | None, optional
        The features to include within the generated project. The available features are
        dynamic and can be modified or extended by the user. See the example section below
        to check the available features. features can also be added post project generation using
        :meth:`HPCProject.insert_feature_into()<pytuflow.HPCProject.insert_feature_into>`.
    crs : str
        The CRS to use for the project in the form of "AUTHORITY:CODE". E.g. the TUFLOW tutorial model
        would be ``"EPSG:32760"``
    create_empties : bool, optional
        Sets whether to generate empty files.
    **kwargs
        Sets any number of variables used in the template files. The available variables are pulled
        from the ``defaults.json`` and ``hpc_defaults.json`` files that are cached in the users home
        directory under ``.tuflow_model_files/project_templates``. Any keyword arguments will override
        the default values listed in the json files. The user is free to modify the defaults or extend them.

    Examples
    --------
    List the available features:

    >>> from pytuflow import HPCProject
    >>> for mod in HPCProject.get_available_features():
    ...     print(mod)
    ad
    estry
    events
    po
    quadtree
    rf
    sgs
    soils
    swmm
    toc
    tutorial

    Or list the features via the CLI:

    .. code-block:: console

        pytuflow-project list-features --engine hpc

    (Re-)Initialise the template files:

    >>> from pytuflow.project import TemplateManager
    >>> manager = TemplateManager(engine_type='hpc')
    >>> manager.init_cache(force=True)

    Initialise the templates via the CLI:

    .. code-block:: console

        pytuflow-project init-templates --engine hpc --force

    Initialise an HPC project with SGS and event features. This example uses the TUFLOW tutorial model CRS.

    >>> project = HPCProject(
    ...     name='Tutorial_Model',
    ...     output_dir='models/TUFLOW',
    ...     features=['sgs', 'events'],
    ...     crs='EPSG:32760',
    ...     create_empties=True
    ... )
    >>> project.validate() # list any errors - empy list is good
    []
    >>> project.create()
    PosixPath('models/TUFLOW')

    Taking the same example as above, and initialising it via the CLI:

    .. code-block:: console

        pytuflow-project create \
            --engine hpc \
            --name Tutorial_Model \
            --output-dir models/TUFLOW \
            --crs "EPSG:32760" \
            --features sgs events

    Initialise an HPC project using GPKG and customise the map outputs.

    >>> project = HPCProject(
    ...     name='Tutorial_Model',
    ...     output_dir='models/TUFLOW',
    ...     crs='EPSG:32760',
    ...     create_empties=True,
    ...     gis_format='GPKG',
    ...     output_formats={
    ...         "XMDF": {
    ...             "data_types": ["h", "v", "d", "q", "ZAEM1"],
    ...             "interval": 3600
    ...         },
    ...         "TIF": {
    ...             "data_types": ["h", "v", "d", "ZAEM1"],
    ...             "interval": 0
    ...         }
    ...     }
    ... )
    >>> project.validate() # list any errors - empy list is good
    []
    >>> project.create()
    PosixPath('models/TUFLOW')

    Initialising the same example via the CLI.

    .. code-block:: console

        pytuflow-project create \
            --engine hpc \
            --name Tutorial_Model \
            --output-dir models/TUFLOW \
            --crs "EPSG:32760" \
            --gis-format GPKG \
            --output-format '{"XMDF": {"data_types": "h v d q ZAEM1", "interval": 3600}, \
                "TIF": {"data_types": "h v d ZAEM1", "interval": 0}}'

    Insert Quadtree into an existing model:

    >>> HPCProject.insert_feature_into('quadtree', 'models/TUFLOW/runs/Tutorial_Model_001.tcf')

    Insert PO int an existing model using the CLI:

    .. code-block:: console

        pytuflow-project insert \
            --engine hpc \
            --cf models/TUFLOW/runs/Tutorial_Model_001.tcf \
            --feature po
    """

    ENGINE_TYPE = 'hpc'
    MAIN_CF_EXT = 'tcf'
    MAIN_CF_CLASS = 'TCF'
    OUTPUT_DIRS = ['runs', 'model', 'bc_dbase', 'results', 'check', 'runs/log']
    EMPTIES_KEY = 'hpc'
    SUPPORTED_GIS_FORMATS = frozenset({'SHP', 'MIF', 'GPKG'})
    BASE_TEMPLATES = [
        ('runs/${model_name}_${iter}.tcf', 'runs/${model_name}_${iter}.tcf'),
        ('model/${model_name}_${iter}.tgc', 'model/${model_name}_${iter}.tgc'),
        ('model/${model_name}_${iter}.tbc', 'model/${model_name}_${iter}.tbc'),
        ('bc_dbase/bc_dbase.csv', 'bc_dbase/bc_dbase.csv'),
        ('model/${model_name}_mat.csv', 'model/${model_name}_mat.csv'),
    ]
    CF_TYPE_MAP: dict[str, dict] = {
        'tgc': {'lhs': 'geometry control file', 'class': 'TGC'},
        'tbc': {'lhs': 'bc control file', 'class': 'TBC'},
        'ecf': {'lhs': 'estry control file', 'class': 'ECF'},
        'qcf': {'lhs': 'quadtree control file', 'class': 'QCF'},
        'adcf': {'lhs': 'ad control file', 'class': 'ADCF'},
        'tscf': {'lhs': 'swmm control file', 'class': 'TSCF'},
        'toc': {'lhs': 'read operating controls file', 'class': 'TOC'},
        'trfc': {'lhs': 'rainfall control file', 'class': 'TRFC'}
    }

    @classmethod
    def _get_feature_base_class(cls):
        from .features._base import HPCBaseFeature
        return HPCBaseFeature


# Keep old name available for any code that imported it directly
_variables_from_tcf_path = _variables_from_cf_path
