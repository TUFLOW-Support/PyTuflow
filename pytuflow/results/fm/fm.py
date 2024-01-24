from pathlib import Path
from typing import Union

from .fm_res_driver import FM_ResultDriver
from ..abc.time_series_result import TimeSeriesResult


PathType = Union[str, Path, None]


class FM_TS(TimeSeriesResult):

    def __init__(self, fpath: Union[PathType, list[PathType]], gxy: PathType, dat: PathType) -> None:
        self._df = None
        self._driver = []
        self.gxy = Path(gxy) if gxy is not None else None
        self.dat = Path(dat) if dat is not None else None
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
            except NotImplementedError as e:
                raise Exception('Flood Modeller result not recognised, supported, or result could be empty')
            except FileNotFoundError as e:
                raise FileNotFoundError(e)
            except Exception as e:
                raise Exception(f'Error loading Flood Modeller result: {e}')

        self.sim_id = self._driver[0].display_name
