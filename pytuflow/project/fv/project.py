from __future__ import annotations

from .._common.project import BaseEngineProject


def get_available_features() -> dict[str, type]:
    """Discover all available FV features from JSON files in the feature cache."""
    return FVProject.get_available_features()


_BASE_TEMPLATES = [
    ('runs/${model_name}_${iter}.fvc', 'runs/${model_name}_${iter}.fvc'),
    ('bc_dbase/bc_dbase.csv', 'bc_dbase/bc_dbase.csv'),
]


class FVProject(BaseEngineProject):
    """TUFLOW FV project generator.

    FV differences from HPC:

    * Primary control file is ``.fvc`` (loaded as :class:`pytuflow.FVC`).
    * No secondary control files (all content lives in the single FVC).
    * GPKG is not a supported GIS format.
    * Output blocks are treated as features — no ``Map Output Formats`` command.
    * FV-specific defaults are loaded from ``fv_defaults.json``.
    """

    ENGINE_TYPE = 'fv'
    MAIN_CF_EXT = 'fvc'
    MAIN_CF_CLASS = 'FVC'
    BASE_TEMPLATES = _BASE_TEMPLATES
    OUTPUT_DIRS = ['runs', 'model', 'model/geo', 'model/gis', 'bc_dbase', 'results', 'check', 'runs/log']
    EMPTIES_KEY = 'fv'
    SUPPORTED_GIS_FORMATS = frozenset({'SHP', 'MIF'})

    @classmethod
    def _get_feature_base_class(cls):
        from .features._base import FVBaseFeature
        return FVBaseFeature
