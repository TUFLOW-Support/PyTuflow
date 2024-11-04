from pathlib import Path

from netCDF4 import Dataset

from .fv_bc_tide_node_strings import FVBCTideNodeStrings
from .fv_bc_tide_nodes import FVBCTideNodes
from .fv_bc_tide_provider import FVBCTideProvider
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
                return 'time' in nc.dimensions and len(nc.dimensions) > 1
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

    def long_plot_result_types(self) -> list[str]:
        # docstring inherited
        return ['Water Level']
