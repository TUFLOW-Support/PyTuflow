try:
    from osgeo import ogr, gdal, osr
except ImportError:
    from .ogr_ import ogr_ as ogr
    from .gdal_ import gdal_ as gdal
    from .osr_ import osr_ as osr
