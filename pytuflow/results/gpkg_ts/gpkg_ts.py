import re
from datetime import datetime
from pathlib import Path
from pytuflow.types import PathLike, TuflowPath

from .gpkg_nodes import GPKGNodes
from .gpkg_channels import GPKGChannels
from .gpkg_ts_base import GPKGBase
from ..abc.time_series_result import TimeSeriesResult
from pytuflow.util.time_util import gpkg_time_series_reference_time



class GPKG_TS(GPKGBase, TimeSeriesResult):
    """Class for handling GeoPackage time series results. The GPKG time series format is a specific format published
     by TUFLOW built on the GeoPackage standard. The format specification is published here:

     `https://wiki.tuflow.com/GPKG_Time_Series_Format_Specification <https://wiki.tuflow.com/GPKG_Time_Series_Format_Specification>`_
     """

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        super(GPKG_TS, self).__init__(fpath)

        # properties
        self._sim_id = None
        self._units = None
        self._reference_time = None
        self._nodes = None
        self._channels = None
        self._gis_point_layer_name = None
        self._gis_line_layer_name = None
        self._gis_region_layer_name = None

    def __repr__(self) -> str:
        if hasattr(self, 'sim_id'):
            return f'<GPKG TS: {self.sim_id}>'
        return '<GPKG TS>'

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        # docstring inherited
        import sqlite3
        try:
            conn = sqlite3.connect(fpath)
        except Exception as e:
            return False
        try:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            version = cur.fetchone()[0]
            valid = True
        except Exception as e:
            valid = False
        finally:
            conn.close()
        return valid

    def looks_empty(self, fpath: Path) -> bool:
        # docstring inherited
        import sqlite3
        try:
            conn = sqlite3.connect(fpath)
        except Exception as e:
            return True
        try:
            cur = conn.cursor()
            cur.execute('SELECT DISTINCT Table_name, Count FROM Timeseries_info;')
            count = sum([int(x[1]) for x in cur.fetchall()])
            empty = count == 0
        except Exception:
            empty = True
        finally:
            conn.close()
        return empty

    def load(self) -> None:
        # docstring inherited
        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        if not self.is_gpkg_ts_res(self.fpath):
            raise ValueError(f'File is not a valid GPKG TS result: {self.fpath}')

    @property
    def sim_id(self) -> str:
        #: str: The simulation ID.
        if self._sim_id is None:
            self._sim_id = re.sub(r'_swmm_ts', '', self.fpath.stem)
        return self._sim_id

    @sim_id.setter
    def sim_id(self, value: str) -> None:
        return

    @property
    def units(self) -> str:
        #: str: The units of the result file, 'metric' or 'imperial'.
        if self._units is None:
            self._reference_time, self._units = self._get_reference_time()
        return self._units

    @units.setter
    def units(self, value: str) -> None:
        return

    @property
    def reference_time(self) -> str:
        #: datetime: Result reference time.
        if self._reference_time is None:
            self._reference_time, self._units = self._get_reference_time()
        return self._reference_time

    @reference_time.setter
    def reference_time(self, value: str) -> None:
        return

    @property
    def gis_point_layer_name(self) -> str:
        #: str: The name of the GIS point layer within the GeoPackage.
        if self._gis_point_layer_name is None:
            try:
                self._open_db()
                self._cur.execute(
                    'SELECT'
                    ' DISTINCT Timeseries_info.Table_name '
                    'FROM'
                    ' Timeseries_info '
                    'INNER JOIN gpkg_geometry_columns'
                    ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                    'WHERE'
                    ' gpkg_geometry_columns.geometry_type_name = "POINT" LIMIT 1;'
                )
                ret = self._cur.fetchone()
                if ret:
                    self._gis_point_layer_name = ret[0]
            except Exception as e:
                raise Exception(f'Error getting GIS point layer name: {e}')
            finally:
                self._close_db()
        return self._gis_point_layer_name

    @gis_point_layer_name.setter
    def gis_point_layer_name(self, value: str) -> None:
        return

    @property
    def gis_line_layer_name(self) -> str:
        #: str: The name of the GIS line layer within the GeoPackage.
        if self._gis_line_layer_name is None:
            try:
                self._open_db()
                self._cur.execute(
                    'SELECT'
                    ' DISTINCT Timeseries_info.Table_name '
                    'FROM'
                    ' Timeseries_info '
                    'INNER JOIN gpkg_geometry_columns'
                    ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                    'WHERE'
                    ' gpkg_geometry_columns.geometry_type_name = "LINESTRING" LIMIT 1;'
                )
                ret = self._cur.fetchone()
                if ret:
                    self._gis_line_layer_name = ret[0]
            except Exception as e:
                raise Exception(f'Error getting GIS line layer name: {e}')
            finally:
                self._close_db()
        return self._gis_line_layer_name

    @gis_line_layer_name.setter
    def gis_line_layer_name(self, value: str) -> None:
        return

    @property
    def gis_region_layer_name(self) -> str:
        #: str: The name of the GIS region layer within the GeoPackage.
        if self._gis_region_layer_name is None:
            try:
                self._open_db()
                self._cur.execute(
                    'SELECT'
                    ' DISTINCT Timeseries_info.Table_name '
                    'FROM'
                    ' Timeseries_info '
                    'INNER JOIN gpkg_geometry_columns'
                    ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                    'WHERE'
                    ' gpkg_geometry_columns.geometry_type_name = "POLYGON" LIMIT 1;'
                )
                ret = self._cur.fetchone()
                if ret:
                    self._gis_region_layer_name = ret[0]
            except Exception as e:
                raise Exception(f'Error getting GIS region layer name: {e}')
            finally:
                self._close_db()
        return self._gis_region_layer_name

    @gis_region_layer_name.setter
    def gis_region_layer_name(self, value: str) -> None:
        return

    @property
    def gis_point_layer(self) -> TuflowPath:
        #: TuflowPath: The path to the GIS point layer.
        lyr = self.gis_point_layer_name
        if lyr:
            return TuflowPath(f'{self.fpath} >> {lyr}')

    @gis_point_layer.setter
    def gis_point_layer(self, value: PathLike) -> None:
        return

    @property
    def gis_line_layer(self) -> TuflowPath:
        #: TuflowPath: The path to the GIS line layer.
        lyr = self.gis_line_layer_name
        if lyr:
            return TuflowPath(f'{self.fpath} >> {lyr}')

    @gis_line_layer.setter
    def gis_line_layer(self, value: PathLike) -> None:
        return

    @property
    def gis_region_layer(self) -> TuflowPath:
        #: TuflowPath: The path to the GIS region layer.
        lyr = self.gis_region_layer_name
        if lyr:
            return TuflowPath(f'{self.fpath} >> {lyr}')

    @gis_region_layer.setter
    def gis_region_layer(self, value: PathLike) -> None:
        return

    @property
    def nodes(self) -> GPKGNodes:
        #: GPKGNodes: Nodes result class object if available.
        if self._nodes is None:
            self._nodes = GPKGNodes(self.fpath, self.gis_point_layer_name)
        return self._nodes

    @nodes.setter
    def nodes(self, value: GPKGNodes) -> None:
        return

    @property
    def channels(self) -> GPKGChannels:
        #: GPKGChannels: Channels result class object if available.
        if self._channels is None:
            self._channels = GPKGChannels(self.fpath, self.gis_line_layer_name)
        return self._channels

    @channels.setter
    def channels(self, value: GPKGChannels) -> None:
        return

    @staticmethod
    def is_gpkg_ts_res(fname: Path) -> bool:
        """Routine determining if file is valid / compatible.

        Parameters
        ----------
        fname : Path
            Path to file.

        Returns
        -------
        bool
            True if file is valid / compatible.
        """
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(fname)
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            version = cur.fetchone()[0]
            valid = bool(version)
        except Exception as e:
            # No need to log. If the table doesn't exist, we just want to return valid as False
            # Logging.error(e, Logging.get_stack_trace())
            valid = False
        finally:
            if conn is not None:
                conn.close()
        return valid

    def _get_reference_time(self) -> tuple[datetime, str]:
        return gpkg_time_series_reference_time(self.fpath)
