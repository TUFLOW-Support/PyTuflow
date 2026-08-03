from __future__ import annotations

from .._common.project import BaseEngineProject


def get_available_features() -> dict[str, type]:
    """Discover all available FV features from JSON files in the feature cache."""
    return FVProject.get_available_features()


class FVProject(BaseEngineProject):
    r"""TUFLOW FV project generator.

    The FV project generator is a highly customisable class for generating
    a FV project from scratch. The class uses template files, modular features, variables,
    and directives, which are fully customisable and extendable by the user.

    When an FV project is created for the first time, the template files are copied
    locally to the users home directory:
    
    - Windows: ``%userprofile%\.tuflow_model_files\project_templates``
    - Linux: ``~/.tuflow_model_files/project_templates``
    
    Subsequent calls will use these cached templates, and the user is free to modify and/or extend them.

    Projects can also be created via the CLI with ``pytuflow-project create --engine fv``.
    See below for examples.

    It is also possible to insert features into an existing project using 
    :meth:`FVProject.insert_feature_into()<pytuflow.FVProject.insert_feature_into>` or via the CLI
    with ``pytuflow-project insert --engine fv``.
    
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
        :meth:`FVProject.insert_feature_into()<pytuflow.FVProject.insert_feature_into>`.
    crs : str
        The CRS to use for the project in the form of "AUTHORITY:CODE". E.g. the TUFLOW tutorial model
        would be ``"EPSG:32760"``
    create_empties : bool, optional
        Sets whether to generate empty files.
    **kwargs
        Sets any number of variables used in the template files. The available variables are pulled
        from the ``defaults.json`` and ``fv_defaults.json`` files that are cached in the users home
        directory under ``.tuflow_model_files/project_templates``. Any keyword arguments will override
        the default values listed in the json files. The user is free to modify the defaults or extend them.

    Examples
    --------
    List the available features:

    >>> from pytuflow import FVProject
    >>> for mod in FVProject.get_available_features():
    ...     print(mod)
    3d
    ad
    outputflux
    outputnc
    outputpoints
    ptm
    salinity
    stm
    structcoeff
    structculv
    structel
    structmat
    structpor
    structtim
    structwall
    structweir
    structweirdz
    temp
    tutorial
    wqm

    Or list the features via the CLI:
    
    .. code-block:: console

        pytuflow-project list-features --engine fvc

    (Re-)Initialise the template files:
    
    >>> from pytuflow.project import TemplateManager
    >>> manager = TemplateManager(engine_type='fv')
    >>> manager.init_cache(force=True)

    Initialise the templates via the CLI:

    .. code-block:: console

        pytuflow-project init-templates --engine fv --force

    Initialise an FV project with Tutorial model set to "On" and an output NetCDF with default settings.
    
    >>> project = FVProject(
    ...     name='Tutorial_Model',
    ...     output_dir='models/TUFLOWFV',
    ...     features=['tutorial', 'outputnc'],
    ...     crs='EPSG:32760',
    ...     create_empties=True
    ... )
    >>> project.validate() # list any errors - empy list is good
    []
    >>> project.create()
    PosixPath('models/TUFLOWFV')

    Taking the same example as above, and initialising it via the CLI:

    .. code-block:: console

        pytuflow-project create \
            --engine fv \
            --name Tutorial_Model \
            --output-dir models/TUFLOWFV \
            --crs "EPSG:32760" \
            --features tutorial outputnc

    Initialise an FV project with Tutorial model set to "On" and an output NetCDF with custom settings. Additionally, set the hardware to be GPU.

    >>> project = FVProject(
    ...     name='Tutorial_Model',
    ...     output_dir='models/TUFLOWFV',
    ...     features=['tutorial', 'outputnc'],
    ...     crs='EPSG:32760',
    ...     create_empties=True,
    ...     hardware='GPU',
    ...     output_interval=300,
    ...     output_params="h, v, d
    ... )
    >>> project.validate() # list any errors - empy list is good
    []
    >>> project.create()
    PosixPath('models/TUFLOWFV')

    Taking the same example as above, and initialising it via the CLI:

    .. code-block:: console

        pytuflow-project create \
            --engine fv \
            --name Tutorial_Model \
            --output-dir models/TUFLOWFV \
            --crs "EPSG:32760" \
            --features tutorial outputnc \
            --hardware GPU \
            --output-interval 300 \
            --output-params "h, v, d"

    Most "features" within the TUFLOW FV project are singular and can only be added once to the project (e.g. "Tutorial Model == On") and if the command exists
    already then nothing will be created or inserted. Some of the "features" are additive and allow multiple insertions.
    Outputs are one such feature, as it might be desirable to split outputs parameters into different files.

    As an example of multiple insertions via the create function, the example below includes water quality in the creation and adds an output NetCDF for both the
    hydrodynamics and the water quality results.

    >>> project = FVProject(
    ...     name='Tutorial_Model',
    ...     output_dir='models/TUFLOWFV',
    ...     features=[
                'tutorial', '3d', 'temp', 'salinity', 'ad', 'wqm'
                {'name': 'outputnc', 'output_interval': 300, 'output_params': 'h, v, d', 'output_suffix': 'HD'},
                {'name': 'outputnc', 'output_interval': 300, 'output_params': 'WQ_ALL', 'output_suffix': 'WQ'},
                {'name': 'outputnc', 'output_interval': 300, 'output_params': 'WQ_Diag_ALL', 'output_suffix': 'WQ_Diag'}
            ],
    ...     crs='EPSG:32760',
    ...     create_empties=True
    ... )
    >>> project.validate() # list any errors - empy list is good
    []
    >>> project.create()
    PosixPath('models/TUFLOWFV')

    Taking the same example as above, and initialising it via the CLI:

    .. code-block:: console
    
        pytuflow-project create \
            --engine fv \
            --name Tutorial_Model \
            --output-dir models/TUFLOWFV \
            --crs "EPSG:32760" \
            --features tutorial 3d temp salinity ad wqm \
                '{"name": "outputnc", "output_interval": 300, "output_params": "h, v, d", "output_suffix": "HD"}' \
                '{"name": "outputnc", "output_interval": 300, "output_params": "WQ_ALL", "output_suffix": "WQ"}' \
                '{"name": "outputnc", "output_interval": 300, "output_params": "WQ_Diag_ALL", "output_suffix": "WQ_Diag"}'
    """

    ENGINE_TYPE = 'fv'
    MAIN_CF_EXT = 'fvc'
    MAIN_CF_CLASS = 'FVC'
    OUTPUT_DIRS = ['runs', 'model', 'model/geo', 'model/gis', 'bc_dbase', 'results', 'check', 'runs/log']
    EMPTIES_KEY = 'fv'
    SUPPORTED_GIS_FORMATS = frozenset({'SHP', 'MIF'})
    BASE_TEMPLATES = [
        ('runs/${model_name}_${iter}.fvc', 'runs/${model_name}_${iter}.fvc'),
        ('bc_dbase/bc_dbase.csv', 'bc_dbase/bc_dbase.csv'),
    ]
    CF_TYPE_MAP: dict[str, dict] = {
        'fvsed': {'lhs': 'sediment control file', 'class': 'FVSed'},
        'fvptm': {'lhs': 'particle tracking control file', 'class': 'FVPTM'},
        'fvwq': {'lhs': '/(?:water quality|wq) control file/i', 'class': 'FVWQ'},
    }

    @classmethod
    def _get_feature_base_class(cls):
        from .features._base import FVBaseFeature
        return FVBaseFeature
