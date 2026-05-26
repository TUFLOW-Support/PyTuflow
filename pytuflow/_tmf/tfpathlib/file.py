import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path, PosixPath, WindowsPath

from .vector_file_open import OGROpen, PyOGRIOOpen
from .raster_open_file import RasterIOOpen, GDALRasterOpen


SPLIT_DATABASE_REGEX = re.compile(r'>>(?![^<]*>>)')

_prefer_gdal = False


def set_prefer_gdal(prefer: bool):
    global _prefer_gdal
    _prefer_gdal = prefer


class TuflowPath(Path):
    """Extension of the :code:`Path` class - :code:`Path` is nicer to use than :code:`os`, but doesn't resolve
    TUFLOW wildcards/variables '<< >>'  that can appear in file path references with TUFLOW control files,
    nor does it handle TUFLOW GPKG style paths :code:`'database >> layername'` very well.

    A number of methods have been overridden to handle GPKG databases, such as the 'glob' method which now works
    to search for layers within a GPKG database.
    """

    def __new__(cls, *args, **kwargs):
        cls = TuflowWindowsPath if os.name == 'nt' else TuflowPosixPath
        if os.name != 'nt' and len(args) == 1 and '\\' in str(args[0]):
            # This is probably a Windows path being read on a POSIX system
            parts = (str(args[0]).replace('\\', '/'),)
        else:
            parts = args

        # noinspection PyUnreachableCode
        if sys.version_info >= (3, 12):
            self = object.__new__(cls)
        else:
            try:
                self = cls._from_parts(parts, init=False)
                self._init()
            except TypeError:
                self = cls._from_parts(parts)

        if args and str(args[0]) and (str(args[0])[-1] == '\\' or str(args[0])[-1] == '/'):
            self._end_slash = True
        else:
            self._end_slash = False

        return self

    def __init__(self, *args):
        if sys.version_info >= (3, 12):
            if os.name != 'nt' and args and '\\' in str(args[0]):
                args_ = [str(a).replace('\\', '/') for a in args]
                super().__init__(*args_)
            else:
                super().__init__(*args)

    def __contains__(self, item):
        if isinstance(item, str):
            return item in str(self)
        else:
            raise TypeError(f'unsupported operand type(s) for in: {type(self)} and {type(item)}')

    def __eq__(self, other):
        path_other = TuflowPath(other)
        if self.lyrname is None and path_other.lyrname is None:
            return self.dbpath == path_other.dbpath
        if self.lyrname is None and path_other.lyrname is not None:
            return False
        if self.lyrname is not None and path_other.lyrname is None:
            return False
        return self.dbpath == path_other.dbpath and self.lyrname.lower() == path_other.lyrname.lower()

    def __hash__(self):
        return hash(str(self))

    def __floordiv__(self, other):
        return self / self.init_case_insensitive_path(other, self.dbpath)

    def _split_db_and_lyr(self) -> tuple[str, str]:
        string = str(self)
        if '>>' in string and string.count('>>') > string.count('<<'):
            return tuple([x.strip() for x in SPLIT_DATABASE_REGEX.split(string, maxsplit=1)][:2])
        if '|layername=' in string:
            dbpath, lyrname = [x.strip() for x in string.split('|layername=', 1)]
            if '|' in lyrname:
                lyrname = lyrname.split('|', 1)[0].strip()
            return dbpath, lyrname
        if string.lower().startswith('netcdf:'):
            dbpath, lyrname = string.split(':', 1)[-1].rsplit(':', 1)
            dbpath = dbpath.strip('"').strip()
            lyrname = lyrname.strip('"').strip()
            return dbpath, lyrname
        if '|' in string:
            dbpath, _ = [x.strip() for x in string.split('|', 1)]
        else:
            dbpath = string
        return dbpath, None

    def _gpkg_layers(self) -> list[str]:
        layers = []
        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT table_name FROM gpkg_contents;")
                layers = [x[0] for x in cur.fetchall()]
        except Exception:
            pass
        return layers

    def _nc_layers(self) -> list[str]:
        try:
            from netCDF4 import Dataset
            with Dataset(self.dbpath, 'r') as nc:
                return [var.lower() for var in nc.variables.keys()]
        except ImportError:
            pass

        try:
            from h5py import File
            with File(self.dbpath, 'r') as h5:
                return [var.lower() for var in h5.keys()]
        except ImportError:
            pass

        raise ImportError('Unable to read NetCDF layers. netCDF4 or h5py is required.')

    @staticmethod
    def _resolve_case_insensitive(path: 'TuflowPath', base_dir: 'TuflowPath') -> 'TuflowPath':
        lyrname = None
        if path.lyrname and path.lyrname != path.stem:
            lyrname = path.lyrname
        if path.dbpath.is_absolute():
            is_abs = True
            parts = path.dbpath.parts[1:]
            current = Path(path.dbpath.root)
        else:
            is_abs = False
            parts = path.dbpath.parts
            current = base_dir if base_dir is not None else Path.cwd()

        new_parts = []
        for part in parts:
            if part == '..':
                current = current.parent
                new_parts.append(part)
                continue
            elif part == '.':
                new_parts.append(part)
                continue

            matches = [
                p for p in current.iterdir()
                if p.name.lower() == part.lower()
            ]

            if not matches:
                raise FileNotFoundError(f"No case-insensitive match for {part} in {current}")

            if len(matches) > 1:
                raise RuntimeError(
                    f"Ambiguous case-insensitive match for {part} in {current}"
                )

            current = matches[0]
            new_parts.append(current.name)

        new_path = current if is_abs else Path(*new_parts)
        ret = TuflowPath(new_path) if lyrname is None else TuflowPath(f'{new_path} >> {lyrname}')

        return ret

    @property
    def suffix(self):
        return os.path.splitext(self.name)[1]

    @property
    def name(self):
        return self.dbpath.name

    @property
    def dbpath(self):
        #: TuflowPath: The database path.
        dbpath, _ = self._split_db_and_lyr()
        return Path(dbpath)

    @property
    def lyrname(self) -> str | None:
        #: str: The layer name if the path is a GIS vector file.
        _, lyrname = self._split_db_and_lyr()
        if lyrname is None and self.suffix.lower() in ['.shp', '.mif', '.mid', '.tab', '.gpkg', '.dbf', '.prj']:
            lyrname = self.dbpath.stem
        return lyrname

    @contextmanager
    def connect(self):
        """Context manager to open a connection to the database."""
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(self.dbpath)
            yield conn
        finally:
            if conn:
                conn.close()

    @staticmethod
    def init_case_insensitive_path(path: str | Path, base_dir: str | Path = '') -> 'TuflowPath':
        if os.name == 'nt':
            return TuflowPath(path)
        path = TuflowPath(path)
        base_dir = TuflowPath(base_dir) if base_dir else None
        try:
            return TuflowPath._resolve_case_insensitive(path, base_dir)
        except FileNotFoundError:
            return TuflowPath(path)

    def geometry_types(self):
        if not self.is_vector_gis():
            raise ValueError('Path is not a vector GIS layer.')
        with self.open_gis() as gis:
            return gis.geometry_types()

    def is_vector_gis(self):
        if self.suffix.lower() in ['.shp', '.prj', '.mif', '.mid', '.tab' ]:
            return True
        if self.suffix.lower() in ['.asc', '.tif', '.flt', '.nc']:
            return False
        if self.suffix.lower() == '.gpkg':
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT table_name, data_type FROM gpkg_contents;")
                layers = {x[0]: x[1] for x in cur.fetchall()}
                if layers.get(self.lyrname) == 'features':
                    return True
        return False

    def is_raster_gis(self):
        if self.suffix.lower() in ['.shp', '.prj', '.mif', '.mid', '.tab' ]:
            return False
        if self.suffix.lower() in ['.asc', '.tif', '.flt', '.nc']:
            return True
        if self.suffix.lower() == '.gpkg':
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT table_name, data_type FROM gpkg_contents;")
                layers = {x[0]: x[1] for x in cur.fetchall()}
                if layers.get(self.lyrname) == 'gridded-data':
                    return True
        return False

    def is_relative_to(self, other, **kwargs):
        path_other = TuflowPath(other)
        return self.dbpath.is_relative_to(path_other.dbpath)

    def relative_to(self, other, **kwargs):
        path_other = TuflowPath(other)
        p = TuflowPath(self.dbpath.relative_to(path_other.dbpath))
        if self.lyrname and self.lyrname != self.stem:
            p = TuflowPath(str(p) + ' >> ' + self.lyrname)
        return p

    def open_gis(self, mode='r', geometry_type: str = None, crs=None):
        """Open the path as a GIS vector dataset.

        Parameters
        ----------
        mode : str, optional
            Open mode. ``'r'`` read-only (default), ``'w'`` create/overwrite layer,
            ``'r+'`` update existing layer (create if absent), ``'a'`` append to layer.
        geometry_type : str, optional
            Geometry type string used when creating a new layer in write modes.
            One of ``'Point'``, ``'LineString'``, ``'Polygon'``, ``'MultiPoint'``,
            ``'MultiLineString'``, ``'MultiPolygon'``. Defaults to unspecified.
        crs : str or pyproj.CRS, optional
            Coordinate reference system for the new layer. Accepts an authority
            string (e.g. ``'EPSG:4326'``), a WKT string, or a :class:`pyproj.CRS`
            object. Ignored for read modes.

        Returns
        -------
        OGROpen or PyOGRIOOpen
            The opened dataset, usable as a context manager.
        """
        from . import has_gdal, has_geopandas

        if _prefer_gdal and has_gdal:
            return OGROpen(self, mode, geometry_type=geometry_type, crs=crs)
        elif has_geopandas:
            return PyOGRIOOpen(self, mode, geometry_type=geometry_type, crs=crs)

        if has_geopandas:
            return PyOGRIOOpen(self, mode, geometry_type=geometry_type, crs=crs)
        elif has_gdal:
            return OGROpen(self, mode, geometry_type=geometry_type, crs=crs)
        raise ImportError('GDAL or GeoPandas is required to open GIS layers.')

    def open_grid(self, mode: str = 'r', band: int = 1):
        from . import has_gdal, has_rasterio

        if _prefer_gdal and has_gdal:
            return GDALRasterOpen(self, mode, band)
        elif has_rasterio:
            return RasterIOOpen(self, mode, band)

        if has_rasterio:
            return RasterIOOpen(self, mode, band)
        elif has_gdal:
            return GDALRasterOpen(self, mode, band)
        raise ImportError('GDAL or Rasterio is required to open raster layers.')

    def split(self, separator, maxsplit=-1):
        """Split the path into parts based on the given separator.

        Parameters
        ----------
        separator : str
            The separator to split the path on.
        maxsplit : int, optional
            The maximum number of splits to perform. The default is -1.

        Returns
        -------
        list[str]
            The split parts of the path.
        """
        return str(self).split(separator, maxsplit)

    def exists(self, **kwargs) -> bool:
        if not self.dbpath.exists():
            return False
        if self.suffix.lower() == '.gpkg':
            layers = self._gpkg_layers()
            return bool(layers)
        elif self.suffix.lower() == '.nc' and str(self).lower().startswith('netcdf:'):
            layers = self._nc_layers()
            return bool(layers)
        return True

    def with_suffix(self, suffix: str):
        return TuflowPath(Path.with_suffix(self, suffix))

    def upper(self):
        """Converts the path to an uppercase string object.

        Returns
        -------
        str
            The path as an uppercase string.
        """
        return str(self).upper()

    def lower(self):
        """Converts the path to an lowercase string object.

        Returns
        -------
        str
            The path as an lowercase string.
        """
        return str(self).lower()

    def is_file(self) -> bool:
        return self.dbpath.is_file()

    def is_dir(self):
        return self.dbpath.is_dir()

    def resolve(self, strict=...):
        """Override method so it will work with TUFLOW style wildcards/variables."""

        try:
            return TuflowPath(Path(os.path.abspath(self)))
        except OSError:
            found = True
            path = TuflowPath(os.path.abspath(self))
            i = 0
            for i, part in enumerate(path.parts):
                if '~' in part:
                    found = True
                    break
            if not found:
                return path
            p = Path(*path.parts[:i])
            try:
                p = p.resolve()
            except OSError:
                pass
            for part in path.parts[i:]:
                p = p / part
            return TuflowPath(p)

    def glob(self, pattern, **kwargs):
        """Override method so can do some stuff with TUFLOW style wildcards/variables and also GPKG databases."""
        p = TuflowPath(pattern)
        self_db, self_lyrname = self._split_db_and_lyr()
        db, lyr = p._split_db_and_lyr()
        glob_lyrname_only = False
        if not db:
            # this means the pattern in only a layer name e.g. TuflowPath(db.gpkg).glob('>> 2d_*')
            glob_lyrname_only = True
            db = Path(self_db)

        if self_lyrname is not None:
            raise NotImplementedError('Must glob using a relative path without a layer name.')

        if lyr is not None and TuflowPath(db).suffix.lower() not in ['.gpkg', '.nc']:
            raise ValueError('Pattern includes a layer name but the file is not a database that supports '
                             'multiple layers (e.g. GPKG or NetCDF).')

        if lyr is None:
            yield from Path(self).glob(pattern)
            return

        iter = [db] if glob_lyrname_only else Path(self).glob(db)

        for p in iter:
            layers = TuflowPath(p)._gpkg_layers() if p.suffix.lower() == '.gpkg' else TuflowPath(p)._nc_layers()
            layers = {x.lower(): x for x in layers}
            if '*' not in lyr:
                if lyr.lower() in layers:
                    yield TuflowPath(f'{p} >> {layers[lyr.lower()]}')
            else:
                lyr_pattern = re.compile('^' + re.escape(lyr).replace('\\*', '.*') + '$', flags=re.IGNORECASE)
                for lyrname in layers:
                    if lyr_pattern.match(lyrname):
                        yield TuflowPath(f'{p} >> {layers[lyrname]}')

    def is_file_binary(self) -> bool:
        """Tests if a file is binary or not.

        Uses method from file(1) behaviour.
        https://github.com/file/file/blob/f2a6e7cb7db9b5fd86100403df6b2f830c7f22ba/src/encoding.c#L151-L228
        """
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        is_binary_string = lambda b: bool(b.translate(None, textchars))
        try:
            with self.open('rb') as f:
                return is_binary_string(f.read(1024))
        except (FileNotFoundError, OSError, TypeError, AttributeError, ValueError):
            return False


class TuflowWindowsPath(WindowsPath, TuflowPath):

    def __str__(self):
        str_ = super().__str__()
        try:
            if self._end_slash:
                str_ = '{0}{1}'.format(str_, os.sep)
        except AttributeError:
            pass

        return str_

    def __truediv__(self, other):
        return TuflowPath(WindowsPath.__truediv__(self, other))

    def __hash__(self):
        return hash(str(self))


class TuflowPosixPath(PosixPath, TuflowPath):

    def __str__(self):
        str_ = str(PosixPath.__str__(self))
        try:
            if self._end_slash:
                str_ = '{0}{1}'.format(str_, os.sep)
        except AttributeError:
            pass

        return str_

    def __truediv__(self, other):
        return TuflowPath(PosixPath.__truediv__(self, other))

    def __hash__(self):
        return hash(str(self))
    #
    # def find_in_walk_dir(self, name, index_=None, ignore_case=False, exclude=None):
    #     """Similar to find_parent but is not restrained by it having to be a direct parent, and will look into
    #     other folders.
    #
    #     Parameters
    #     ----------
    #     name : str
    #         The folder name to search for.
    #     index_ : int, optional
    #         The number of folders to search up from the path. The default is None.
    #     ignore_case : bool, optional
    #         Whether to ignore case when searching. The default is False.
    #     exclude : str, optional
    #         The folder to exclude from the search. The default is None.
    #
    #     Returns
    #     -------
    #     TuflowPath
    #         The path to the folder if found, otherwise None.
    #     """
    #     return super().find_in_walk_dir(name, index_, ignore_case, exclude)
