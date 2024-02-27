import re
from datetime import datetime
from pathlib import Path
from typing import Any
from ..types import PathLike

import pandas as pd

try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None

from ..abc.time_series_result import TimeSeriesResult
from .tpc_time_series_result_item import TPCResultItem
from .tpc_nodes import TPCNodes
from .tpc_channels import TPCChannels
from .tpc_maximums import TPCMaximums
from .tpc_po import TPCPO
from .tpc_rl import TPCRL
from ..time_util import default_reference_time, nc_time_series_reference_time


NAME_MAP = {'velocities': 'Velocity', 'energy levels': 'Energy'}
NC_MAP = {'1d channel losses': '1d losses', '1d node regime': None, '1d channel regime': '1d flow regime',
          '1d mass balance errors': '1d mass balance error'}


class TPC(TimeSeriesResult):

    def __init__(self, fpath: PathLike) -> None:
        self._df = None
        self.format_version = -1
        super().__init__(fpath)

    def __repr__(self) -> str:
        if hasattr(self, 'sim_id'):
            return f'<TPC: {self.sim_id}>'
        return '<TPC>'

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        if fpath.suffix.upper() != '.TPC':
            return  False
        try:
            with fpath.open() as f:
                line = f.readline()
                if not line.startswith('Format Version =='):
                    return False
        except Exception as e:
            return False
        return True

    def looks_empty(self, fpath: Path) -> bool:
        TARGET_LINE_COUNT = 10  # fairly arbitrary
        try:
            df = pd.read_csv(self.fpath, sep=' == ', engine='python', header=None)
            if df.shape[0] < TARGET_LINE_COUNT:
                return True
            if df.shape[1] < 2:
                return True
            node_count = int(df[df.iloc[:,0] == 'Number 1D Nodes'].iloc[0,1])
            channel_count = int(df[df.iloc[:,0] == 'Number 1D Channels'].iloc[0,1])
            rlp_count = int(df[df.iloc[:,0] == 'Number Reporting Location Points'].iloc[0,1])
            rll_count = int(df[df.iloc[:,0] == 'Number Reporting Location Lines'].iloc[0,1])
            rlr_count = int(df[df.iloc[:,0] == 'Number Reporting Location Regions'].iloc[0,1])
            po_count = 0
            for row in df.itertuples():
                if row[1].startswith('2D'):
                    po_count += 1
            if node_count + channel_count + rlp_count + rll_count + rlr_count + po_count == 0:
                return True
            return False
        except Exception as e:
            return True

    def load(self) -> None:
        try:
            self._df = pd.read_csv(self.fpath, sep=' == ', engine='python', header=None)
        except Exception as e:
            raise Exception(f'Error loading file: {e}')

        self.units = self._get_property('Units')
        self.sim_id = self._get_property('Simulation ID')
        self.format_version = int(self._get_property('Format Version'))
        self.storage_format = self._get_property('Time Series Output Format', 'CSV')
        self.nc = None
        if 'NC' in self.storage_format and 'CSV' in self.storage_format:  # can be both 'NC' and 'CSV'
            if Dataset is None:
                self.storage_format = 'CSV'
            else:
                self.storage_format = 'NC'
        if self.storage_format == 'NC':
            self.nc = self.fpath.parent / self._get_property('NetCDF Time Series')
        self.reference_time = self._get_reference_time()

        self._load_1d_results()
        self._load_po_results()
        self._load_rl_results()

    def _get_property(self, name: str, default: any = None) -> Any:
        try:
            prop = self._df[self._df.iloc[:,0] == name].iloc[0,1]
        except Exception as e:
            prop = default
        return prop

    def _get_property_index(self, name: str) -> int:
        try:
            ind = self._df[self._df.iloc[:,0] == name].index[0]
        except Exception as e:
            ind = -1
        return ind

    def _get_reference_time(self):
        prop = self._get_property('Reference Time')
        if prop is None:
            if self.storage_format == 'NC':
                try:
                    reference_time, _ = nc_time_series_reference_time(self.nc)
                    return reference_time
                except Exception as e:
                    pass
            return default_reference_time
        return datetime.strptime(prop, '%d/%m/%Y %H:%M:%S')

    def _load_nodes(self) -> TPCNodes:
        node_info = self.fpath.parent / self._get_property('1D Node Info')
        nodes = TPCNodes(node_info)
        if self.storage_format == 'NC':
            nodes.nc = self.nc
        return nodes

    def _load_channels(self) -> TPCChannels:
        chan_info = self.fpath.parent / self._get_property('1D Channel Info')
        channels = TPCChannels(chan_info)
        if self.storage_format == 'NC':
            channels.nc = self.nc
        return channels

    def _1d_name_extract(self, name: str) -> str:
        return name.replace('1D ', '').replace('1d', '')

    def _1d_result_name(self, name: str) -> str:
        name = self._1d_name_extract(name)
        if name.lower() in NAME_MAP:
            name = NAME_MAP[name.lower()]
        if name[-1] == 's' and not name.endswith('Losses'):
            name = name[:-1]
        return name

    def _2d_name_extract(self, name: str) -> str:
        name = name.replace('2D ', '').replace('2d ', '')
        name = re.sub(r'(point|line|region)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\[\d+]', '', name).strip()
        return name

    def _2d_result_name(self, name: str) -> str:
        name = self._2d_name_extract(name)
        if name.lower() in NAME_MAP:
            name = NAME_MAP[name.lower()]
        if name[-1] == 's':
            name = name[:-1]
        return name

    def _rl_name_extract(self, name: str) -> str:
        return re.sub(r'Reporting Location (Points|Lines|Regions)', '', name, flags=re.IGNORECASE).strip()

    def _rl_result_name(self, name: str) -> str:
        name = self._rl_name_extract(name)
        if name.lower() in NAME_MAP:
            name = NAME_MAP[name.lower()]
        if name[-1] == 's':
            name = name[:-1]
        return name

    def _nc_id(self, name: str, domain: str) -> str:
        name = NC_MAP.get(name.lower(), name.lower())
        if name is None:
            return None
        if domain.lower() == '1d':
            return f'{"_".join(self._1d_name_extract(name).split(" ")[1:]).lower()}_{domain.lower()}'
        elif domain.lower() == '2d':
            return f'{"_".join(self._2d_name_extract(name).split(" ")[1:]).lower()}_{domain.lower()}'
        elif domain.lower() == '0d':
            return f'{"_".join(self._rl_name_extract(name).split(" ")).lower()}_rl'

    def _expand_property(self, row: tuple[int, str, str]) -> tuple[str, Path]:
        _, name_, relpath = row
        if relpath == 'NONE':
            p = None
        else:
            p = self.fpath.parent / relpath
        return name_, p

    def _load_1d_results(self) -> None:
        node_count = int(self._get_property('Number 1D Nodes'))
        if node_count > 0:
            self.nodes = self._load_nodes()
            relpath = self._get_property('1D Node Maximums')
            if relpath:
                fpath = self.fpath.parent / relpath
                self.nodes.maximums = TPCMaximums(fpath)
            i = self._get_property_index('1D Node Maximums') + 1
            for row in self._df.iloc[i:].itertuples():
                name_, fpath = self._expand_property(row)
                if name_ == '1D Channel Maximums':
                    break
                elif '1D' not in name_:
                    break
                id = self._nc_id(name_, '1d')
                if id is None or fpath is None:
                    continue
                name = self._1d_result_name(name_)
                self.nodes.load_time_series(name, fpath, self.reference_time, 1, id)

        chan_count = int(self._get_property('Number 1D Channels'))
        if chan_count > 0:
            self.channels = self._load_channels()
            relpath = self._get_property('1D Channel Maximums')
            if relpath:
                fpath = self.fpath.parent / relpath
                self.channels.maximums = TPCMaximums(fpath)
            i = self._get_property_index('1D Channel Maximums') + 1
            for row in self._df.iloc[i:].itertuples():
                name_, fpath = self._expand_property(row)
                if name_ == '1D Channel Maximums':
                    break
                elif '1D' not in name_:
                    break
                _, name_, relpath = row
                id = self._nc_id(name_, '1d')
                if id is None or fpath is None:
                    continue
                name = self._1d_result_name(name_)
                if name == 'Channel Losses':
                    for loss_type in ['Entry', 'Additional', 'Exit']:
                        self.channels.load_time_series(name, fpath, self.reference_time, 1, id, loss_type)
                else:
                    self.channels.load_time_series(name, fpath, self.reference_time, 1, id)

    def _load_po_results(self) -> None:
        df = self._df[self._df.iloc[:,0].str.contains('2D')]
        for row in df.itertuples():
            if not self.po:
                self.po = TPCPO(None)
                self.po.nc = self.nc
            name_, fpath = self._expand_property(row)
            id = self._nc_id(name_, '2d')
            if id is None or fpath is None:
                continue
            name = self._2d_result_name(name_)
            self.po.load_time_series(name, fpath, self.reference_time, 1, id)

    def _load_rl_results(self) -> None:
        rl_point_count = self._get_property('Number Reporting Location Points')
        if rl_point_count:
            rl_point_count = int(rl_point_count)
        else:
            rl_point_count = 0
        if rl_point_count:
            df = self._df[self._df.iloc[:,0].str.contains('Reporting Location Points')]
            for row in df.itertuples():
                name_, fpath = self._expand_property(row)
                if 'Number' in name_:
                    continue
                if not self.rl:
                    self.rl = TPCRL(None)
                    self.rl.nc = self.nc
                id = self._nc_id(name_, '0d')
                if id is None or fpath is None:
                    continue
                name = self._rl_result_name(name_)
                if name.lower() == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximums(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, self.reference_time, 1, id)

        rl_line_count = self._get_property('Number Reporting Location Lines')
        if rl_line_count:
            rl_line_count = int(rl_line_count)
        else:
            rl_line_count = 0
        if rl_line_count:
            df = self._df[self._df.iloc[:, 0].str.contains('Reporting Location Lines')]
            for row in df.itertuples():
                if 'Number' in row[1]:
                    continue
                if not self.rl:
                    self.rl = TPCRL(None)
                _, name_, relpath = row
                if relpath == 'NONE':
                    continue
                id = self._nc_id(name_, '0d')
                if id is None:
                    continue
                name = self._rl_result_name(name_)
                fpath = self.fpath.parent / relpath
                if name.lower() == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximums(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, self.reference_time, 1, id)

        rl_region_count = self._get_property('Number Reporting Location Regions')
        if rl_region_count:
            rl_region_count = int(rl_region_count)
        else:
            rl_region_count = 0
        if rl_region_count:
            df = self._df[self._df.iloc[:, 0].str.contains('Reporting Location Regions')]
            for row in df.itertuples():
                if 'Number' in row[1]:
                    continue
                if not self.rl:
                    self.rl = TPCRL(None)
                _, name_, relpath = row
                if relpath == 'NONE':
                    continue
                id = self._nc_id(name_, '0d')
                if id is None:
                    continue
                name = self._rl_result_name(name_)
                fpath = self.fpath.parent / relpath
                if name.lower() == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximums(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, self.reference_time, 1, id)
