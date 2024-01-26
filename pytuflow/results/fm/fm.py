from pathlib import Path
from typing import Union

from .fm_nodes import FMNodes
from .fm_res_driver import FM_ResultDriver
from .gxy import GXY
from .dat import Dat
from ..abc.time_series_result import TimeSeriesResult
from ..time_util import default_reference_time


PathType = Union[str, Path, None]


class FM_TS(TimeSeriesResult):

    def __init__(self, fpath: Union[PathType, list[PathType]], gxy: PathType, dat: PathType) -> None:
        self._df = None
        self._driver = []
        self._id_list = None
        self.gxy_fpath = Path(gxy) if gxy is not None else None
        self.dat_fpath = Path(dat) if dat is not None else None
        self.gxy = None
        self.dat = None
        super().__init__(fpath)

    def __repr__(self) -> str:
        if hasattr(self, 'sim_id'):
            return f'<FM TS: {self.sim_id}>'
        return '<TM TS>'

    def load(self) -> None:
        if not isinstance(self.fpath, list):
            self.fpath = [self.fpath]

        for fpath in self.fpath:
            try:
                self._driver.append(FM_ResultDriver(fpath))
                if self._id_list is None:
                    self._id_list = self._driver[0].ids
                else:
                    if self._id_list != self._driver[-1].ids:
                        raise Exception('Result IDs do not match')
            except NotImplementedError as e:
                raise Exception('Flood Modeller result not recognised, supported, or result could be empty')
            except FileNotFoundError as e:
                raise FileNotFoundError(e)
            except Exception as e:
                raise Exception(f'Error loading Flood Modeller result: {e}')

        self.sim_id = self._driver[0].display_name
        for driver in self._driver:
            driver.reference_time = default_reference_time

        if self.gxy_fpath is not None:
            self.gxy = GXY(self.gxy_fpath)

        if self.dat_fpath is not None:
            self.dat = Dat(self.dat_fpath)

        self.nodes = FMNodes(self.fpath[0], self._id_list, self.gxy, self.dat)
