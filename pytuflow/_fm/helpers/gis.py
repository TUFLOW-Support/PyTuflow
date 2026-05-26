import logging
import os.path
import typing
from pathlib import Path

import numpy as np
try:
    from osgeo import ogr, gdal
    from osgeo.ogr import DataSource
    from osgeo.ogr import Layer
    has_gdal = True
except ImportError:
    has_gdal = False
    DataSource = 'Datasource'
    Layer = 'Layer'
from collections import OrderedDict

from .settings import get_fm2estry_settings
from ..fm_to_estry_types import PathLike


logger = logging.getLogger('pytuflow')
settings = get_fm2estry_settings()

if has_gdal:
    ogr.UseExceptions()
    gdal.UseExceptions()


def gdal_error() -> bool:
    """Returns a bool if there was a GDAL error or not"""

    global b_gdal_error
    return b_gdal_error


def gdal_error_handler(err_class: int, err_num: int, err_msg: str) -> None:
    """Custom python gdal error handler - if there is a failure, need to let GDAL finish first."""
    if not has_gdal:
        raise ImportError('GDAL is required to handle GDAL errors.')
    errtype = {
            gdal.CE_None:'None',
            gdal.CE_Debug:'Debug',
            gdal.CE_Warning:'Warning',
            gdal.CE_Failure:'Failure',
            gdal.CE_Fatal:'Fatal'
    }
    err_msg = err_msg.replace('\n',' ')
    err_class = errtype.get(err_class, 'None')
    if err_class.lower() == 'failure':
        global b_gdal_error
        b_gdal_error = True

    # skip these warning msgs
    if 'Normalized/laundered field name:' in err_msg:
        return
    if 'width 256 truncated to 254' in err_msg:
        return

    if err_class == gdal.CE_Failure or err_class == gdal.CE_Fatal:
        logger.error('GDAL {0}'.format(err_class.upper()))
        logger.error('{1} Number: {0}'.format(err_num, err_class))
        logger.error('{1} Message: {0}'.format(err_msg, err_class))
    elif err_class == gdal.CE_Warning:
        logger.warning('GDAL {0}'.format(err_class.upper()))
        logger.warning('{1} Number: {0}'.format(err_num, err_class))
        logger.warning('{1} Message: {0}'.format(err_msg, err_class))
    elif gdal.CE_Debug:
        logger.debug('GDAL {0}'.format(err_class.upper()))
        logger.debug('{1} Number: {0}'.format(err_num, err_class))
        logger.debug('{1} Message: {0}'.format(err_msg, err_class))


def init_gdal_error_handler() -> None:
    """Initialise GDAL error handler"""
    if not has_gdal:
        return
    global b_gdal_error
    b_gdal_error = False
    gdal.PushErrorHandler(gdal_error_handler)


def open_vector_ds(dbpath: Path) -> DataSource:
    if not has_gdal:
        raise ImportError('GDAL is required to open vector files.')
    dbpath = Path(dbpath)
    if dbpath.exists():
        ds = settings.gis_driver_.Open(str(dbpath), 1)
        lyr = ds.GetLayer()
        if lyr:
            if not lyr.TestCapability('DeleteLayer'):  # if we can't delete layers, we must recreate the datasource
                lyr = None
                ds = None
                settings.gis_driver_.DeleteDataSource(str(dbpath))
                ds = settings.gis_driver_.CreateDataSource(str(dbpath))
    else:
        if not dbpath.parent.exists():
            dbpath.parent.mkdir(parents=True)
        ds = settings.gis_driver_.CreateDataSource(str(dbpath))
    return ds


def open_vector_lyr(ds: DataSource, lyrname: str, geom_type: int, field_map: dict) -> Layer:
    if not has_gdal:
        raise ImportError('GDAL is required to open vector layers.')
    lyr = ds.GetLayer(lyrname)
    if lyr is not None:
        lyr = None
        ds.DeleteLayer(lyrname)
    lyr = ds.CreateLayer(lyrname, settings.crs_, geom_type)
    for k, v in field_map.items():
        if settings.gis_format == 'SHP' and len(k) > 10:
            k = k[:10]
        f = ogr.FieldDefn(k, v['type'])
        if 'width' in v:
            f.SetWidth(v['width'])
        if 'prec' in v:
            f.SetPrecision(v['prec'])
        lyr.CreateField(f)
    return lyr


def vector_geometry_as_array(filepath: PathLike) -> np.ndarray:
    """Returns vector geometry as an array. Will read entire geometry into memory. This routine requires GDAL.

    The return array is a 3D array dimensioned by (n_features, n_points, 2) where n_features is the number of features,
    n_points is the maximum number of points in any feature (with other features padded with nans), and 2 is
    the x and y coordinate.

    Examples
    --------
    >>> # read a shape file that has 3 line features, each with only 2 points
    >>> a = vector_geometry_as_array('path/to/shapefile.shp')
    >>> a.shape
    (3, 2, 2)
    >>> # return the x, y coordinates of the first feature
    >>> a[0]  # or a[0,:,:]
    array([[ 293083.70347101, 6178052.82197938],
           [ 293385.71925746, 6177994.3866685 ]])
    >>> # remove nans from feature if required
    >>> a[0][~np.isnan(a[0]).any(axis=1)]
    array([[ 293083.70347101, 6178052.82197938],
           [ 293385.71925746, 6177994.3866685 ]])

    Parameters
    ----------
    filepath : PathLike
        Path to the vector file.

    Returns
    -------
    np.ndarray
        3D numpy array of geometry
    """
    if not has_gdal:
        raise ImportError('GDAL is required to read vector files.')
    gdal.UseExceptions()
    filepath = str(filepath)
    lyrname = None
    if ' >> ' in filepath:
        filepath, lyrname = filepath.split(' >> ', 1)
    dataset = ogr.Open(filepath)
    if dataset is None:
        logger.error('ERROR invalid file passed to -crs argument: {0}'.format(filepath))
        return None
    try:
        if lyrname:
            layer = dataset.GetLayerByName(lyrname)
        else:
            layer = dataset.GetLayer()
    except Exception as e:
        logger.error(e)
        dataset = None  # this closes the layer
        return None

    feats = []
    max_npoints = 0
    for feature in layer:
        geom = feature.GetGeometryRef()
        max_npoints = max(geom.GetPointCount(), max_npoints)
        feats.append(geom.GetPoints())

    for i, feat in enumerate(feats):
        if len(feat) < max_npoints:
            f = list(feat) + [(np.nan, np.nan) for x in range(max_npoints - len(feat))]
            feats[i] = tuple(f)

    dataset, layer = None, None

    return np.array(feats)


class FeatureMap:

    def __init__(self):
        self.geom = ''
        self.attributes = OrderedDict()


def default_value(field_type: int) -> typing.Any:
    if not has_gdal:
        raise ImportError('GDAL is required to get default values for field types.')
    if field_type == ogr.OFTInteger:
        return 0
    elif field_type == ogr.OFTReal:
        return 0.0
    elif field_type == ogr.OFTString:
        return ''


def get_driver_name_from_extension(driver_type: str, ext: PathLike) -> str:
    """Return the GDAL/OGR driver name based on the file extension. This routine requires GDAL.

    Parameters
    ----------
    driver_type : str
        'raster' or 'vector'
    ext : PathLike
        File or file extension to search for.

    Returns
    -------
    str
        GDAL/OGR driver name.
    """
    if not has_gdal:
        raise ImportError('GDAL is required to get driver name from extension.')

    if not ext:
        return

    if ext[0] != '.':
        ext = os.path.splitext(ext)[1]

    ext = ext.lower()
    if ext[0] == '.':
        ext = ext[1:]

    for i in range(gdal.GetDriverCount()):
        drv = gdal.GetDriver(i)
        md = drv.GetMetadata_Dict()
        if ('DCAP_RASTER' in md and driver_type == 'raster') or ('DCAP_VECTOR' in md and driver_type == 'vector'):
            if not drv.GetMetadataItem(gdal.DMD_EXTENSIONS):
                continue
            driver_extensions = drv.GetMetadataItem(gdal.DMD_EXTENSIONS).split(' ')
            for drv_ext in driver_extensions:
                if drv_ext.lower() == ext:
                    return drv.ShortName


if __name__ == '__main__':
    print('This file is not the entry point. Use fm_to_estry.py')
