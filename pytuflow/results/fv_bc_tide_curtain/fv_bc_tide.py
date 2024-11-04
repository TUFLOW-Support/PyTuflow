import re
from pathlib import Path
from typing import Union

from netCDF4 import Dataset

from .fv_bc_tide_node_strings import FVBCTideNodeStrings
from .fv_bc_tide_nodes import FVBCTideNodes
from .fv_bc_tide_provider import FVBCTideProvider
from .. import Iterator
from ..abc.time_series_result import TimeSeriesResult
from pytuflow.pytuflow_types import PathLike


class FVBCTide(TimeSeriesResult):
    """Class for handling FV BC Tide Curtain Data."""

    def __init__(self, nc_fpath: PathLike, gis_ns_fpath: PathLike, use_local_time: bool = True) -> None:
        #: Path: Path to the FV tide netCDF file.
        self.nc_fpath = Path(nc_fpath)
        #: Path: Path to the GIS node string file.
        self.gis_ns_fpath = Path(gis_ns_fpath)
        #: bool: Uses local time.
        self.use_local_time = use_local_time
        #: FVBCTideNodes: FV BC Tide Nodes object.
        self.nodes = None
        #: FVBCNodeString: FV BC Node String object.
        self.node_strings = None
        #: FVBCTideNCProvider: FV BC Tide provider object.
        self.provider = None
        super().__init__(nc_fpath)

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        # docstring inherited
        try:
            with Dataset(fpath) as nc:
                hastime = 'time' in nc.dimensions and len(nc.dimensions) > 1
                if not hastime:
                    return False
                vars = [x for x in nc.variables.keys() if re.findall(r'^ns.*_wl$', x)]
                has_res = len(vars) > 0
                return has_res
        except Exception:
            return False

    def looks_empty(self, fpath: Path) -> bool:
        # docstring inherited
        with Dataset(fpath) as nc:
            return len(nc.dimensions['time']) == 0

    def load(self, *args, **kwargs) -> None:
        # docstring inherited
        self.provider = FVBCTideProvider(self.nc_fpath, self.gis_ns_fpath, self.use_local_time)
        self.sim_id = self.provider.display_name
        self.nodes = FVBCTideNodes(self.provider)
        self.node_strings = FVBCTideNodeStrings(self.provider)

    def init_iterator(self, *args) -> Iterator:
        # docstring inherited
        if args:
            return Iterator(*args)
        return Iterator(self.nodes, self.node_strings)

    def long_plot_result_types(self) -> list[str]:
        # docstring inherited
        return ['Water Level']

    def node_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        # docstring inherited
        if self.nodes:
            if not result_type:
                return self.nodes.ids(None)
            return self.ids(result_type, '2d node')
        return []

    def node_string_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """Returns the node string IDs for the given result type(s).

        node_string_ids() is equivalent to using '2d node_string' as the domain in
        :meth:`ids() <pytuflow.results.FVBCTide.ids>`.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case-sensitive) or a
            well known short name e.g. 'q', 'v', 'h' etc. If no result type is provided, all result types will be
            searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        if self.node_strings:
            if not result_type:
                return self.node_strings.ids(None)
            return self.ids(result_type, '2d node_string')
        return []

    def node_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        # docstring inherited
        if self.nodes:
            if not id:
                return self.nodes.result_types(None)
            return self.result_types(id, '2d node')
        return []

    def node_string_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """Returns a list of the result types for the given node string ID(s).

        node_string_result_types() is equivalent to using '2d node_string' as the domain in
        :meth:`result_types() <pytuflow.results.TPC.result_types>`.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.nodes:
            if not id:
                return self.node_strings.result_types(None)
            return self.result_types(id, '2d node_string')
        return []
