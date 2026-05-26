from pathlib import Path

try:
    from osgeo import osr, ogr
    from osgeo.osr import SpatialReference
    has_gdal = True
except ImportError:
    has_gdal = False
    SpatialReference = 'SpatialReference'


class CRS:

    def __init__(self, string: str) -> None:
        self.string = string.strip('"')
        self.crs = self._parse(string)
        if not has_gdal:
            raise ImportError('GDAL is not installed, unable to initialise CRS class.')

    def _parse(self, string: str) -> SpatialReference:
        if ':' in string:
            return self._from_auth(string)
        elif Path(string).suffix or '>>' in string:
            return self._from_file(string)
        else:  # assume wkt
            return self._from_wkt(string)

    def _from_wkt(self, string: str) -> SpatialReference:
        return osr.SpatialReference(string)

    def _from_file(self, fpath: str) -> SpatialReference:
        ds, lyr = None, None
        if Path(fpath).suffix.upper() == '.MIF':
            ds = ogr.GetDriverByName('MapInfo File').Open(fpath)
            lyr = ds.GetLayer()
        elif Path(fpath).suffix.upper() == '.SHP':
            ds = ogr.GetDriverByName('ESRI Shapefile').Open(fpath)
            lyr = ds.GetLayer()
        elif Path(fpath).suffix.upper() == '.GPKG':
            ds = ogr.GetDriverByName('GPKG').Open(fpath)
            lyr = ds.GetLayer(Path(fpath).stem)
        elif '>>' in fpath:
            dbname, lyrname = [x.strip() for x in fpath.split('>>', 1)]
            ds = ogr.GetDriverByName('GPKG').Open(fpath)
            lyr = ds.GetLayer(lyrname)
        elif Path(fpath).suffix.upper() == '.PRJ':
            with open(fpath) as f:
                prj = f.read()
            return self._from_wkt(prj)
        else:
            from .gis import get_driver_name_from_extension
            raster = False
            driver_name = get_driver_name_from_extension('vector', Path(fpath).suffix)
            if driver_name is None:
                driver_name = get_driver_name_from_extension('raster', Path(fpath).suffix)
                raster = True
            if driver_name:
                ds = ogr.GetDriverByName(driver_name).Open(fpath)
                lyr = ds.GetLayer()
        if ds:
            if raster:
                crs = ds.GetSpatialRef()
            else:
                crs = lyr.GetSpatialRef()
            ds, lyr = None, None
            return crs

    def _from_auth(self, string: str) -> SpatialReference:
        auth, code = string.split(':', 1)
        sr = osr.SpatialReference()
        if auth.upper() == 'EPSG':
            sr.ImportFromEPSG(int(code))
            return sr
        elif auth.upper() == 'ESRI':
            sr.ImportFromESRI(int(code))
            return sr
