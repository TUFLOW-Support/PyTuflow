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
from contextlib import contextmanager

from ..._pytuflow_types import PathLike, TuflowPath
from ..._tmf import Geom, Feature
from ..._tmf.tmf.tuflow_model_files.gis import GPKG, ogr_basic_geom_type
from ..._tmf.tmf.tuflow_model_files.gis import GISAttributes

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


@contextmanager
def open_gis(fpath):
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

        yield lyr
    finally:
        ds, lyr = None, None  # closes the file


def point_gis_file_to_dict(fpath: PathLike):
    d = {}
    i = 0
    with TuflowPath(fpath).open_gis() as lyr:
        geom_types = lyr.geometry_types()
        if 'Point' not in geom_types and 'MultiPoint' not in geom_types:
            raise ValueError(f'File {fpath} does not contain point geometries.')
        id_fields = ['Id', 'Label', 'Name']
        for feature in lyr:
            fi = -1
            for id_field in id_fields:
                fi = feature.field_index(id_field)
                if fi != -1:
                    break
            name = feature[fi] if fi != -1 else f'pnt{i+1}'
            i += 1

            points = feature.geom.points()
            if len(points) == 1:
                d[name] = points[0]
                continue

            for j, pnt in enumerate(points):
                # name the point parts as a, b, c, ...
                d[f'{name}_{chr(97 + j)}'] = pnt

    return d


def line_gis_file_to_dict(fpath: PathLike):
    d = {}
    i = 0
    p = TuflowPath(fpath)
    with p.open_gis() as lyr:
        geom_types = lyr.geometry_types()
        if 'LineString' not in geom_types and 'MultiLineString' not in geom_types:
            raise ValueError(f'Layer {p.lyrname} is not a line-string layer.')
        id_fields = ['Id', 'Label', 'Name']
        for feature in lyr:
            fi = -1
            for id_field in id_fields:
                fi = feature.field_index(id_field)
                if fi != -1:
                    break
            name = feature[fi] if fi != -1 else f'line{i + 1}'
            i += 1
            lines = feature.geom.lines()
            if len(lines) == 1:
                d[name] = lines[0]
                continue

            for j, line in enumerate(lines):
                # name the point parts as a, b, c, ...
                d[f'{name}_{chr(97 + j)}'] = line

    return d
