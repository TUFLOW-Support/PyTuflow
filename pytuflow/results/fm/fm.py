import os
from datetime import datetime
from pathlib import Path
from typing import Union
from collections import OrderedDict

import pandas as pd

from ..types import PathLike, TimeLike

from .fm_channels import FMChannels
from .fm_nodes import FMNodes
from .fm_res_driver import FM_ResultDriver
from .gxy import GXY
from .dat import Dat
from ..abc.time_series_result import TimeSeriesResult
from ..time_util import default_reference_time, closest_time_index


class FM_TS(TimeSeriesResult):

    def __init__(self, fpath: Union[PathLike, list[PathLike]], gxy: PathLike, dat: PathLike) -> None:
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

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        """Return True if the file looks like this class."""
        return True  # check is done when figuring out the driver

    def looks_empty(self, fpath: Path) -> bool:
        """Return True if the file looks empty."""
        return False

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
            self.dat.load()

        self.nodes = FMNodes(self.fpath[0], self._id_list, self.gxy, self.dat)
        for driver in self._driver:
            for res_type in driver.result_types:
                self.nodes.load_time_series(res_type, driver.df, driver.reference_time, driver.timesteps)

        if self.gxy is not None:
            self.channels = FMChannels(self.fpath[0], [], self.gxy, self.dat)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        df = super().connectivity(ids)

        # convert uid to id and remove junctions
        df_ = df.copy()
        df_['US Type'] = [self.dat.unit(x).type for x in df['US Node']]
        df_['DS Type'] = [self.dat.unit(x).type for x in df['DS Node']]
        df1 = df_[df_['US Type'] != 'junction']
        df2 = df_[df_['DS Type'] != 'junction']
        assert df1.shape == df2.shape, 'Should not be here - [FM Connectivity] df1.shape != df2.shape'
        df1['DS Node'] = df2['DS Node'].tolist()
        df1['DS Invert'] = df2['DS Invert'].tolist()
        df = df1[df.columns]
        for index, row in df.iterrows():
            df.loc[index, 'US Node'] = self.dat.unit(row['US Node']).id
            df.loc[index, 'DS Node'] = self.dat.unit(row['DS Node']).id
        self.lp_1d.df = df
        return df

    def long_plot(self,
                  ids: Union[str, list[str]],
                  result_type: Union[str, list[str]],
                  time: TimeLike
                  ) -> pd.DataFrame:
        if not self.nodes or not self.channels:
            return Exception('DAT file required for long plotting')

        if not isinstance(ids, list):
            ids = [ids] if ids else []

        ids_ = []
        for id_ in ids:
            try:
                dns_chans = self.nodes.df.loc[id_, 'Dns Channels']
                if dns_chans.any():
                    for chan in dns_chans:
                        if len(chan) == 1:
                            ids_.append(chan[0])
                            break
                    if not ids_:
                        raise ValueError(f'Invalid ID {id_} - check id is not a junction')
            except KeyError:
                continue
        return super().long_plot(ids_, result_type, time)
