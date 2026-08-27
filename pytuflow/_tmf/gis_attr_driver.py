import typing
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
# noinspection PyProtectedMember
try:
    from dbfread import DBF
    has_dbf_read = True
except ImportError:
    DBF = 'DBF'
    has_dbf_read = False

from .tfpathlib import TuflowPath
from .tmf_types import PathLike

try:
    from osgeo import ogr
    has_gdal = True
except ImportError:
    from .stubs.ogr_ import ogr_ as ogr
    has_gdal = False

if not has_dbf_read and not has_gdal:
    raise ImportError('Requires either GDAL or dbfread library')

import re

_VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\s\\-]*$")

def _safe_identifier(name: str) -> str:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return '"' + name.replace('"', '""') + '"'


T = typing.TypeVar("T")


class GISAttributes(typing.Generic[T], Iterable[T]):
    """Utility class for iterating over a GIS layer to obtain the attributes."""

    def __iter__(self) -> typing.Generator[OrderedDict, None, None]:
        pass

    def __new__(cls, fpath: PathLike) -> object:
        if has_gdal:
            cls = GDALGISAttributes
            return super().__new__(cls)
        fpath = TuflowPath(fpath)
        if '>>' in fpath:
            fpath = fpath.split(' >> ')[0]
        fpath = Path(fpath)
        if fpath.suffix.lower() == '.dbf' or fpath.suffix.lower() == '.shp':
            cls = DBFAttributes
        elif fpath.suffix.lower() == '.mid' or fpath.suffix.lower() == '.mif':
            cls = MIDAttributes
        elif fpath.suffix.lower() == '.gpkg':
            cls = GPKGAttributes
        return super().__new__(cls)

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            The file path to the GIS file.
        """
        self.fpath = TuflowPath(fpath)
        self._db = None
        self.open()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self) -> None:
        """Open the GIS file for reading."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the GIS file."""
        raise NotImplementedError


class GDALGISAttributes(GISAttributes):

    def __init__(self, fpath: PathLike) -> None:
        from .gis import get_driver_name_from_extension
        fpath = TuflowPath(fpath)
        self._driver = get_driver_name_from_extension('vector', fpath.suffix)
        self._lyr = None
        self._ds = None
        super().__init__(fpath)

    def __iter__(self):
        for feat in self._lyr:
            d = OrderedDict()
            for i in range(feat.GetFieldCount()):
                fld = feat.GetFieldDefnRef(i)
                d[fld.GetName()] = feat.GetField(i)
            yield d

    def open(self) -> None:
        self._ds = ogr.Open(str(self.fpath.dbpath))
        self._lyr = self._ds.GetLayer(self.fpath.lyrname)

    def close(self) -> None:
        self._lyr = None
        self._ds = None


class DBFAttributes(GISAttributes):
    """Utility class for iterating over a SHP/DBF file to obtain the attributes."""

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        fpath = TuflowPath(fpath).dbpath
        if fpath.suffix.lower() == '.shp':
            if fpath.with_suffix('.dbf').exists():
                fpath = fpath.with_suffix('.dbf')
            elif fpath.with_suffix('.DBF').exists():
                fpath = fpath.with_suffix('.DBF')
            else:
                raise FileNotFoundError(f'Accompanying DBF file not found for: {self.fpath}')
        super().__init__(fpath)

    def __iter__(self) -> typing.Generator[OrderedDict, None, None]:
        for record in self._db:
            yield record

    def open(self) -> None:
        # docstring inherited
        self._db = DBF(self.fpath)

    def close(self) -> None:
        # docstring inherited
        self._db = None


class MIDAttributes(GISAttributes):
    """Utility class for iterating over a MIF/MID file to obtain the attributes."""

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        fpath = TuflowPath(fpath).dbpath
        self._col_names = []
        if fpath.suffix.lower() == '.mif':
            self._mif = fpath
            if fpath.with_suffix('.mid').exists():
                fpath = fpath.with_suffix('.mid')
            elif fpath.with_suffix('.MID').exists():
                fpath = fpath.with_suffix('.MID')
            else:
                raise FileNotFoundError(f'Accompanying MID file not found for: {fpath}')
        else:
            if fpath.with_suffix('.mif').exists():
                self._mif = fpath.with_suffix('.mif')
            elif fpath.with_suffix('.MIF').exists():
                self._mif = fpath.with_suffix('.MIF')
            else:
                raise FileNotFoundError(f'Accompanying MIF file not found for: {fpath}')
        super().__init__(fpath)

    def __iter__(self) -> typing.Generator[OrderedDict, None, None]:
        for line in self._db:
            yield OrderedDict(zip(self._col_names, [x.strip(' \t\n"\'') for x in line.split(',')]))

    def open(self) -> None:
        # docstring inherited
        self._db = self.fpath.open()
        ncol = 0
        with self._mif.open() as f:
            for line in f:
                if line.startswith('Columns'):
                    ncol = int(line.split()[1])
                    for i in range(ncol):
                        self._col_names.append(f.readline().split()[0])
                    break
        if not ncol:
            raise Exception(f'MIF file must have at least one attribute column: {self._mif}')

    def close(self) -> None:
        # docstring inherited
        self._db.close()
        self._db = None


class GPKGAttributes(GISAttributes):
    """Utility class for iterating over a GPKG file to obtain the attributes."""

    def __init__(self, fpath: TuflowPath) -> None:
        fpath = TuflowPath(fpath)
        self._tname = fpath.lyrname
        fpath = fpath.dbpath
        self._tname = self._get_case_insensitive_table_name(fpath, self._tname)
        self._geom_col = self._get_geom_col(fpath, self._tname)
        self._fid_col = self._get_fid_col(fpath, self._tname)
        super().__init__(fpath)

    def __iter__(self) -> typing.Generator[OrderedDict, None, None]:
        import sqlite3
        try:
            self._db = sqlite3.connect(self.fpath)
            self._cursor = self._db.cursor()
            tname_quoted = _safe_identifier(self._tname)
            self._cursor.execute(f'SELECT * FROM {tname_quoted};')  # nosec B608
            for row in self._cursor:
                inds = [i for i, x in enumerate(self._cursor.description) if x[0] not in (self._fid_col, self._geom_col)]
                yield OrderedDict([(self._cursor.description[i][0], row[i]) for i in inds])
        except sqlite3.Error:
            pass
        finally:
            if self._db is not None:
                self._db.close()
            self._cursor = None
            self._db = None

    def open(self) -> None:
        # docstring inherited
        pass

    def close(self) -> None:
        # docstring inherited
        pass

    @staticmethod
    def _get_case_insensitive_table_name(fpath: PathLike, tname: str) -> str:
        import sqlite3
        db = None
        try:
            db = sqlite3.connect(fpath)
            cursor = db.cursor()
            cursor.execute(
                'SELECT name FROM sqlite_master WHERE type="table" AND name=? COLLATE NOCASE;',
                (tname,)
            )
            tname = cursor.fetchone()[0]
        except sqlite3.Error:
            tname = tname
        finally:
            if db is not None:
                db.close()
        return tname

    @staticmethod
    def _get_geom_col(fpath: PathLike, tname: str) -> str:
        import sqlite3
        db = None
        try:
            db = sqlite3.connect(fpath)
            cursor = db.cursor()
            cursor.execute(
                'SELECT column_name FROM gpkg_geometry_columns WHERE table_name=?;',
                (tname,)
            )
            geom_col = cursor.fetchone()[0]
        except sqlite3.Error:
            geom_col = 'geometry'
        finally:
            if db is not None:
                db.close()
        return geom_col

    @staticmethod
    def _get_fid_col(fpath: PathLike, tname: str) -> str:
        import sqlite3
        db = None
        try:
            db = sqlite3.connect(fpath)
            cursor = db.cursor()
            cursor.execute('SELECT name FROM PRAGMA_TABLE_INFO(?) WHERE pk = 1;', (tname,))
            fid_col = cursor.fetchone()[0]
        except sqlite3.Error:
            fid_col = 'fid'
        finally:
            if db is not None:
                db.close()
        return fid_col
