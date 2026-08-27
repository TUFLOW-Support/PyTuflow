from .file import TuflowPath, set_prefer_gdal
from enum import Enum

try:
    from osgeo import gdal
    has_gdal = True
except ImportError:
    has_gdal = False

try:
    import rasterio
    has_rasterio = True
except ImportError:
    has_rasterio = False

try:
    import pyproj
    has_pyproj = True
except ImportError:
    has_pyproj = False

try:
    import geopandas
    has_geopandas = True
except ImportError:
    has_geopandas = False


class GisFormat(Enum):
    Unknown = 0
    MIF = 1
    SHP = 2
    GPKG = 3
    ASC = 4
    TIF = 5
    FLT = 6
    NC = 7


def ogr_format(file: TuflowPath, no_ext_is_mif: bool = True) -> GisFormat:
    if str(file).startswith('CoordSys') or TuflowPath(file).stem.startswith('CoordSys'):
        return GisFormat.MIF
    if file.dbpath.suffix.upper() in ['.XF4', '.XF8']:
        return GisFormat.Unknown
    if file.dbpath.suffix.upper() in ['.SHP', '.PRJ']:
        return GisFormat.SHP
    if file.dbpath.suffix.upper() in ['.MIF', '.MID']:
        return GisFormat.MIF
    if file.dbpath.suffix.upper() == '.GPKG':
        return GisFormat.GPKG
    if file.dbpath.suffix.upper() == '' and no_ext_is_mif:
        return GisFormat.MIF
    elif file.dbpath.suffix.upper() == '':
        return GisFormat.GPKG
    return GisFormat.Unknown


def gdal_format(file, no_ext_is_gpkg=False, no_ext_is_nc=False) -> GisFormat:
    """Returns the GDAL driver name based on the extension of the file reference."""
    if file.dbpath.suffix.upper() in ['.XF4', '.XF8']:
        return GisFormat.Unknown
    if file.dbpath.suffix.upper() == '.ASC' or file.dbpath.suffix.upper() == '.TXT' or file.dbpath.suffix.upper() == '.DEM':
        return GisFormat.ASC
    if file.dbpath.suffix.upper() == '.FLT':
        return GisFormat.FLT
    if file.dbpath.suffix.upper() == '.GPKG':
        return GisFormat.GPKG
    if file.dbpath.suffix.upper() == '.NC':
        return GisFormat.NC
    if file.dbpath.suffix.upper() == '.TIF' or file.dbpath.suffix.upper() == '.TIFF' or file.dbpath.suffix.upper() == '.GTIF' \
            or file.dbpath.suffix.upper() == '.GTIFF':
        return GisFormat.TIF
    if file.dbpath.suffix.upper() == '' and no_ext_is_gpkg:
        return GisFormat.GPKG
    elif file.dbpath.suffix.upper() == '' and no_ext_is_nc:
        return GisFormat.NC
    return GisFormat.Unknown


def get_driver_name_from_gis_format(gis_format: GisFormat) -> str | None:
    """Returns the GDAL/OGR driver name based on the GIS format."""
    if gis_format == GisFormat.SHP:
        return 'ESRI Shapefile'
    elif gis_format == GisFormat.MIF:
        return 'MapInfo File'
    elif gis_format == GisFormat.GPKG:
        return 'GPKG'
    elif gis_format == GisFormat.ASC:
        return 'AAIGrid'
    elif gis_format == GisFormat.TIF:
        return 'GTiff'
    elif gis_format == GisFormat.FLT:
        return 'ENVI'
    elif gis_format == GisFormat.NC:
        return 'NetCDF'
    else:
        return None


def ogr_geom_type_to_string(geom_type):
    """Convert OGR geometry type to a string e.g. PointM -> Point"""
    from osgeo import ogr
    while geom_type - 1000 > 0:
        geom_type -= 1000

    if geom_type == ogr.wkbPoint:
        return 'Point'
    elif geom_type == ogr.wkbLineString:
        return 'LineString'
    elif geom_type == ogr.wkbPolygon:
        return 'Polygon'
    elif geom_type == ogr.wkbMultiPoint:
        return 'MultiPoint'
    elif geom_type == ogr.wkbMultiLineString:
        return 'MultiLineString'
    elif geom_type == ogr.wkbMultiPolygon:
        return 'MultiPolygon'
    else:
        return 'Unknown'
