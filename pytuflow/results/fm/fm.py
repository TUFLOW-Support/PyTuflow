import os
from datetime import datetime
from pathlib import Path
from typing import Union
from collections import OrderedDict

import pandas as pd

from pytuflow.pytuflow_types import PathLike, TimeLike

from .fm_channels import FMChannels
from .fm_nodes import FMNodes
from .fm_res_driver import FM_ResultDriver
from pytuflow.fm import GXY
from pytuflow.fm import DAT
from ..abc.time_series_result import TimeSeriesResult
from pytuflow.util.time_util import default_reference_time, closest_time_index


class FM_TS(TimeSeriesResult):
    """Flood Modeller Time Series Result."""

    def __init__(self, fpath: Union[PathLike, list[PathLike]], gxy: PathLike = None, dat: PathLike = None) -> None:
        """
        Parameters
        ----------
        fpath: Union[PathLike, list[PathLike]]
            Flood modeller result file path(s). The file paths can be CSVs exported via the Flood Modeller GUI,
            the python flood modeller-api, or the raw ZZN files.
        gxy: PathLike, optional
            Path to the GXY file.
        dat: PathLike, optional
            Path to the DAT file.
        """
        self._df = None
        self._driver = []
        self._id_list = None
        #: Path: Path to the GXY file.
        self.gxy_fpath = Path(gxy) if gxy is not None else None
        #: Path: Path to the DAT file.
        self.dat_fpath = Path(dat) if dat is not None else None
        #: GXY: GXY object.
        self.gxy = None
        #: DAT: DAT object.
        self.dat = None
        super().__init__(fpath)

    def __repr__(self) -> str:
        if hasattr(self, 'sim_id'):
            return f'<FM TS: {self.sim_id}>'
        return '<TM TS>'

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        # docstring inherited
        return True  # check is done when figuring out the driver

    def looks_empty(self, fpath: Path) -> bool:
        # docstring inherited
        return False

    def load(self) -> None:
        # docstring inherited
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

        if self.dat_fpath is not None:
            self.dat = DAT(self.dat_fpath)

        if self.gxy_fpath is not None:
            self.gxy = GXY(self.gxy_fpath)

        self.nodes = FMNodes(self.fpath[0], self._id_list, self.gxy, self.dat)
        for driver in self._driver:
            for res_type in driver.result_types:
                self.nodes.load_time_series(res_type, driver.df, driver.reference_time, driver.timesteps)

        if self.gxy is not None or self.dat is not None:
            self.channels = FMChannels(self.fpath[0], [], self.gxy, self.dat)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        # docstring inherited
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
        # docstring inherited
        if self.dat is None:
            raise Exception('DAT file required for long plotting')

        if not isinstance(ids, list):
            ids = [ids] if ids else []

        ids_ = []
        for id_ in ids:
            try:
                dns_chans = self.nodes.df.loc[[id_], 'Dns Channels']
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
