"""GIS module.

This module contains a collection of useful functions for working with GIS files. Typically, these functions are
light-weight and do not require GDAL (there are a few exceptions).

Examples
--------
The :class:`GPKG` class can be used to see what's inside

>>> from pytuflow.util.gis import GPKG
>>> db = GPKG('path/to/file.gpkg')
>>> for lyr in db.layers():
>>>     print(lyr)
2d_bc_EG00_001_L
2d_code_EG00_001_R
2d_loc_EG00_001_L
2d_mat_EG00_001_R
projection
>>> '2d_bc_EG00_001_L' in db  # case-sensitive
True
>>> for lyr in db.glob('*_L'):  # glob-style pattern matching
>>>     print(lyr)
2d_bc_EG00_001_L
2d_loc_EG00_001_L

The :class:`GISAttributes` class can be used to extract attributes from GIS files (without GDAL)

>>> from pytuflow.util.gis import GISAttributes
>>> for attr in GISAttributes('path/to/0d_rl_001_L.shp'):
>>>     print(attr)
OrderedDict([('Name', 'RL_03')])
OrderedDict([('Name', 'RL_04')])
OrderedDict([('Name', 'RL_05')])
"""

from pytuflow._tmf.tmf.convert_tuflow_model_gis_format.conv_tf_gis_format.helpers.gis import GPKG
from pytuflow._tmf.tmf.tuflow_model_files.db.drivers.gis_attr_driver import GISAttributes

try:
    from osgeo import ogr
    from fm_to_estry.helpers.gis import vector_geometry_as_array, get_driver_name_from_extension
    has_gdal = True
except ImportError:
    ogr = None
    vector_geometry_as_array = None
    get_driver_name_from_extension = None
    has_gdal = False
