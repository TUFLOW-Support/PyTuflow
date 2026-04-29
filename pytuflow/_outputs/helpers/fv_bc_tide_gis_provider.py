from .lp_gis_driver import LongProfileGIS
from ..._pytuflow_types import PathLike


class FVBCTideGISProvider(LongProfileGIS):

    def __init__(self, path: PathLike, *args, **kwargs) -> None:
        super().__init__(path, 'ID')
