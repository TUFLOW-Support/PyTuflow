import re
from datetime import datetime
from pathlib import Path
from typing import Union

from .gpkg_nodes import GPKGNodes
from .gpkg_channels import GPKGChannels
from .gpkg_time_series_result_item import GPKGResultItem
from ..abc.time_series_result import TimeSeriesResult
from ..time_util import gpkg_time_series_reference_time


class GPKG_TS(TimeSeriesResult):

    def __init__(self, fpath: Union[str, Path]) -> None:
        self._db = None
        self._cur = None

        super().__init__(fpath)

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

    def load(self) -> None:
        from sqlite3 import DatabaseError

        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        if not self.is_gpkg_ts_res(self.fpath):
            raise ValueError(f'File is not a valid GPKG TS result: {self.fpath}')

    @property
    def sim_id(self) -> str:
        if self._sim_id is None:
            self._sim_id = re.sub(r'_swmm_ts', '', self.fpath.stem)
        return self._sim_id

    @sim_id.setter
    def sim_id(self, value: str) -> None:
        return

    @property
    def units(self) -> str:
        if self._units is None:
            self._reference_time, self._units = self._get_reference_time()
        return self._units

    @units.setter
    def units(self, value: str) -> None:
        return

    @property
    def reference_time(self) -> str:
        if self._reference_time is None:
            self._reference_time, self._units = self._get_reference_time()
        return self._reference_time

    @reference_time.setter
    def reference_time(self, value: str) -> None:
        return

    @property
    def gis_point_layer_name(self) -> str:
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
    def nodes(self) -> GPKGNodes:
        if self._nodes is None:
            self._nodes = GPKGNodes(self.fpath, self.gis_point_layer_name)
        return self._nodes

    @nodes.setter
    def nodes(self, value: GPKGNodes) -> None:
        return

    @property
    def channels(self) -> GPKGChannels:
        if self._channels is None:
            self._channels = GPKGChannels(self.fpath, self.gis_line_layer_name)
        return self._channels

    @channels.setter
    def channels(self, value: GPKGChannels) -> None:
        return

    @staticmethod
    def is_gpkg_ts_res(fname: Path) -> bool:
        """Routine determining if file is valid / compatible."""
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

    def _open_db(self) -> None:
        import sqlite3
        if self._db is None:
            self._db = sqlite3.connect(self.fpath)
            self._cur = self._db.cursor()

    def _close_db(self) -> None:
        if self._db is not None:
            self._cur = None
            self._db.close()
            self._db = None

    def _get_reference_time(self) -> tuple[datetime, str]:
        return gpkg_time_series_reference_time(self.fpath)
