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
from pytuflow._pytuflow_types import PathLike, TuflowPath
from pytuflow._tmf.tmf.convert_tuflow_model_gis_format.conv_tf_gis_format.helpers.gis import GPKG, ogr_basic_geom_type
from pytuflow._tmf.tmf.tuflow_model_files.db.drivers.gis_attr_driver import GISAttributes

try:
    from osgeo import ogr
    from osgeo.ogr import Layer
    from fm_to_estry.helpers.gis import vector_geometry_as_array, get_driver_name_from_extension
    has_gdal = True
except ImportError:
    ogr = None
    Layer = 'Layer'
    vector_geometry_as_array = None
    get_driver_name_from_extension = None
    has_gdal = False


def point_gis_file_to_dict(fpath: PathLike):
    if not has_gdal:
        raise ImportError('GDAL python libraries are not installed or cannot be imported.')

    p = TuflowPath(fpath)
    if not p.dbpath.exists():
        raise FileNotFoundError(f'File does not exist: {p.dbpath}')

    driver_name = get_driver_name_from_extension('vector', p.dbpath.suffix)
    if not driver_name:
        raise ValueError(f'Unsupported file extension: {p.dbpath.suffix}')

    ds = ogr.GetDriverByName(driver_name).Open(str(p.dbpath))
    if not ds:
        raise RuntimeError(f'Failed to open {p.dbpath}')

    try:
        lyr = ds.GetLayer(p.lyrname)
        if not lyr:
            raise RuntimeError(f'Failed to open layer {p.lyrname}')

        if ogr_basic_geom_type(lyr.GetGeomType()) != ogr.wkbPoint:
            raise ValueError(f'Layer {p.lyrname} is not a point layer.')

        d = {}
        i = 0
        for feature in lyr:
            geom = feature.GetGeometryRef()
            fi = feature.GetFieldIndex('Name')
            if fi == -1:
                fi = feature.GetFieldIndex('name')
            name = feature[fi] if fi != -1 else f'pnt{i+1}'
            i += 1
            pnts = geom.GetPoints()
            if len(pnts) == 1:
                d[name] = pnts[0]
            else:
                for j, p in enumerate(pnts):
                    if fi == -1:
                        name = f'{name}_{j+1}'
                        i += 1
                    else:
                        name = f'{name}_{j+1}'
                    d[name] = p
    finally:
        dataset, layer = None, None

    return d
