from pathlib import Path

import numpy as np

try:
    import pyproj
except ImportError:
    pyproj = None


class RasterOpen:

    def __init__(self, file_path: str | Path, mode = 'r', band: int = 1):
        self.mode = 'r'
        self.band = band
        self.file_path = file_path
        if mode == 'w' or mode == 'r+':
            raise NotImplementedError("RasterOpen currently only supports read mode ('r').")
        self.ds = None
        self.dx = None
        self.dy = None
        self.ox = None
        self.oy = None
        self.ncol = None
        self.nrow = None
        self.no_data_value = None
        self.flip_y = False
        self.flip_x = False
        self.open()

    def __repr__(self):
        return f"RasterOpen(file_path={self.file_path}, mode={self.mode})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def crs(self):
        raise NotImplementedError

    def crs_wkt(self) -> str:
        raise NotImplementedError

    def crs_auth(self) -> str:
        raise NotImplementedError

    def as_array(self):
        pass

    def open(self):
        pass

    def close(self):
        pass


class RasterIOOpen(RasterOpen):

    def crs(self):
        if pyproj is not None and self.ds.crs is not None:
            return pyproj.CRS.from_string(self.crs_auth())
        return self.ds.crs

    def crs_wkt(self) -> str:
        if self.ds.crs is not None:
            return self.ds.crs.to_wkt()
        return ''

    def crs_auth(self) -> str:
        if self.ds.crs is not None:
            return self.ds.crs.to_string()
        return 'UNKNOWN'

    def open(self):
        import rasterio
        self.ds = rasterio.open(self.file_path)
        self.ncol = self.ds.width
        self.nrow = self.ds.height
        geotransform = self.ds.transform
        if geotransform[4] < 0:
            self.dy = -geotransform[4]
            self.oy = geotransform[5] - (self.nrow * self.dy)
            self.flip_y = True
        else:
            self.dy = geotransform[4]
            self.oy = geotransform[5]
        if geotransform[1] < 0:
            self.dx = -geotransform[0]
            self.ox = geotransform[2] - (self.ncol * self.dx)
            self.flip_x = True
        else:
            self.dx = geotransform[0]
            self.ox = geotransform[2]
        self.no_data_value = self.ds.nodatavals[self.band - 1]

    def close(self):
        if self.ds:
            self.ds.close()
            self.ds = None

    def as_array(self):
        if not self.ds:
            raise RuntimeError("Dataset is not open.")
        data = self.ds.read(self.band)
        if self.flip_x:
            data = np.fliplr(data)
        if self.flip_y:
            data = np.flipud(data)
        return data


class GDALRasterOpen(RasterOpen):

    def crs(self):
        if pyproj is not None:
            return pyproj.CRS.from_string(self.crs_auth())
        return self.ds.GetSpatialRef()

    def crs_wkt(self) -> str:
        return self.ds.GetSpatialRef().ExportToWkt()

    def crs_auth(self) -> str:
        sr = self.ds.GetSpatialRef()
        return f'{sr.GetAuthorityName(None)}:{sr.GetAuthorityCode(None)}'

    def open(self):
        from osgeo import gdal
        self.ds = gdal.Open(str(self.file_path), gdal.GA_ReadOnly)
        if not self.ds:
            raise FileNotFoundError(f"Could not open file: {self.file_path}")
        self.ncol = self.ds.RasterXSize
        self.nrow = self.ds.RasterYSize
        geotransform = self.ds.GetGeoTransform()
        if geotransform[5] < 0:
            self.dy = -geotransform[5]
            self.oy = geotransform[3] - (self.nrow * self.dy)
            self.flip_y = True
        else:
            self.dy = geotransform[5]
            self.oy = geotransform[3]
        if geotransform[1] < 0:
            self.dx = -geotransform[1]
            self.ox = geotransform[0] - (self.ncol * self.dx)
            self.flip_x = True
        else:
            self.dx = geotransform[1]
            self.ox = geotransform[0]
        band = self.ds.GetRasterBand(self.band)
        self.no_data_value = band.GetNoDataValue()

    def close(self):
        if self.ds:
            self.ds = None  # GDAL handles closing automatically when the object is deleted

    def as_array(self):
        if not self.ds:
            raise RuntimeError("Dataset is not open.")
        band = self.ds.GetRasterBand(self.band)
        data = band.ReadAsArray()
        if self.flip_x:
            data = np.fliplr(data)
        if self.flip_y:
            data = np.flipud(data)
        return data
