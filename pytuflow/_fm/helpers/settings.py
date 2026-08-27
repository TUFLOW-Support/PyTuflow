import os
import sys
import typing
from pathlib import Path

from .crs import CRS

try:
    from osgeo import ogr, osr
    from osgeo.osr import SpatialReference
    has_gdal = True
except ImportError:
    has_gdal = False
    SpatialReference = 'SpatialReference'

from .singleton import Singleton
from ..fm_to_estry_types import PathLike


class Settings(metaclass=Singleton):

    def __init__(self) -> None:
        self._dat_fpath = None
        self._gis_format = 'GPKG'
        self.outname = None
        self.output_dir = Path(os.getcwd())
        self.has_gdal_ = has_gdal
        self.gis_driver_ = None
        if has_gdal:
            self.gis_driver_ = ogr.GetDriverByName('GPKG')
        self.gis_ext_ = '.gpkg'
        self.xs_gis_length = 20.
        self.group_db = True
        self.single_nwk = False
        self.single_tab = False
        self.crs_ = None
        self.arch_bridge_approach = 'BARCH'
        self.arch_bridge_culv_approach = 'MULTI'

    def __str__(self) -> str:
        # return in format of "key: value" for every key that doesn't start or end with '_'
        return '\n'.join(['  {0}: {1}'.format(
            *[k, getattr(self, k)]) for k in dir(self) if not k.startswith('_') and not k.endswith('_') and not callable(getattr(self, k))]
        )

    @property
    def dat_fpath_(self) -> Path:
        return self._dat_fpath

    @dat_fpath_.setter
    def dat_fpath_(self, value: PathLike) -> None:
        if value is not None:
            self._dat_fpath = Path(value)
            self.outname = self._dat_fpath.stem
            self.output_dir = self.output_dir / self.outname

    @property
    def gis_format(self) -> str:
        return self._gis_format

    @gis_format.setter
    def gis_format(self, value: str) -> None:
        self._gis_format = value.upper()
        if self._gis_format == 'GPKG':
            if has_gdal:
                self.gis_driver_ = ogr.GetDriverByName('GPKG')
            self.gis_ext_ = '.gpkg'
        elif self._gis_format == 'SHP':
            if has_gdal:
                self.gis_driver_ = ogr.GetDriverByName('ESRI Shapefile')
            self.gis_ext_ = '.shp'
            self.group_db = False
        elif self._gis_format == 'MIF':
            if has_gdal:
                self.gis_driver_ = ogr.GetDriverByName('MapInfo File')
            self.gis_ext_ = '.mif'
            self.group_db = False
        elif self._gis_format == 'TAB':
            if has_gdal:
                self.gis_driver_ = ogr.GetDriverByName('MapInfo File')
            self.gis_ext_ = '.tab'
            self.group_db = False

    @property
    def crs(self) -> str:
        if self.crs_ is None:
            return None
        if hasattr(self.crs_, 'GetAuthorityName'):
            # OGR SpatialReference
            return f'{self.crs_.GetAuthorityName(None)}:{self.crs_.GetAuthorityCode(None)}'
        if hasattr(self.crs_, 'to_authority'):
            # pyproj.CRS
            auth = self.crs_.to_authority()
            if auth:
                return f'{auth[0]}:{auth[1]}'
            return self.crs_.to_wkt()
        return str(self.crs_)

    @crs.setter
    def crs(self, crs: typing.Union[str, SpatialReference]) -> None:
        if crs is None:
            self.crs_ = None
            return
        # Accept pyproj.CRS directly — store as-is so callers can pass it
        # through to TuflowPath.open_gis() which supports pyproj.CRS natively.
        if hasattr(crs, 'to_authority'):
            self.crs_ = crs
            return
        if has_gdal:
            if isinstance(crs, str):
                self.crs_ = CRS(crs).crs
            else:
                self.crs_ = crs

    def conversion_options(self, co: dict) -> None:
        for key, item in co.items():
            key = key.lower()
            if hasattr(self, key):
                a = getattr(self, key)
                if isinstance(a, bool):
                    b = True if item.lower() in ['true', 't', 'on', 'yes', '1', 'y'] else False
                    setattr(self, key, b)
                elif isinstance(a, int):
                    setattr(self, key, int(item))
                elif isinstance(a, float):
                    setattr(self, key, float(item))
                elif isinstance(a, Path):
                    setattr(self, key, Path(item))
                else:
                    setattr(self, key, item)
            else:
                raise ValueError(f'Invalid conversion option: {key}')


_SETTINGS = Settings()

def get_fm2estry_settings() -> Settings:
    for k, v in sys.modules.items():  # probably very naughty, but ensures that the same settings instance is used across all modules, even if they import it in different ways
        if k.endswith('fm_to_estry.helpers.settings'):
            return v._SETTINGS
    return _SETTINGS
