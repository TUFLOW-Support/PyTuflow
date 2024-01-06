import re
from pathlib import Path
from typing import Union, Any

import pandas as pd

from .abc.time_series_result import TimeSeriesResult
from .abc.tpc_abc import TPCResultItem
from .nodes.nodes_tpc import TPCNodes
from .channels.channels_tpc import TPCChannels
from .maximum.maximum_tpc import TPCMaximum
from .po.po_tpc import TPCPO
from .rl.rl_tpc import TPCRL


NAME_MAP = {'velocities': 'velocity', 'energy levels': 'energy'}


class TPC(TimeSeriesResult):

    def __init__(self, fpath: Union[str, Path]) -> None:
        self._df = None
        self.format_version = -1
        super().__init__(fpath)

    def __repr__(self) -> str:
        if hasattr(self, 'sim_id'):
            return f'<TPC: {self.sim_id}>'
        return '<TPC>'

    def load(self) -> None:
        try:
            self._df = pd.read_csv(self.fpath, sep=' == ', engine='python', header=None)
        except Exception as e:
            raise f'Error loading TPC file: {e}'

        self.units = self._get_property('Units')
        self.sim_id = self._get_property('Simulation ID')
        self.format_version = int(self._get_property('Format Version'))

        self._load_1d_results()
        self._load_po_results()
        self._load_rl_results()

    def conv_result_type_name(self, result_type: str) -> str:
        return TPCResultItem.conv_result_type_name(result_type)

    def _get_property(self, name: str) -> Any:
        try:
            prop = self._df[self._df.iloc[:,0] == name].iloc[0,1]
        except Exception as e:
            prop = None
        return prop

    def _get_property_index(self, name: str) -> int:
        try:
            ind = self._df[self._df.iloc[:,0] == name].index[0]
        except Exception as e:
            ind = -1
        return ind

    def _load_nodes(self) -> TPCNodes:
        node_info = self.fpath.parent / self._get_property('1D Node Info')
        nodes = TPCNodes(node_info)
        return nodes

    def _load_channels(self) -> TPCChannels:
        chan_info = self.fpath.parent / self._get_property('1D Channel Info')
        channels = TPCChannels(chan_info)
        return channels

    def _1d_result_name(self, name: str) -> str:
        name = name.replace('1D ', '').lower()
        if name in NAME_MAP:
            name = NAME_MAP[name]
        if name[-1] == 's':
            name = name[:-1]
        return name

    def _2d_result_name(self, name: str) -> str:
        name = name.replace('2D ', '').lower()
        name = re.sub(r'(point|line|region)', '', name)
        name = re.sub(r'\[\d+]', '', name).strip()
        if name in NAME_MAP:
            name = NAME_MAP[name]
        if name[-1] == 's':
            name = name[:-1]
        return name

    def _rl_result_name(self, name: str) -> str:
        name = re.sub(r'Reporting Location (Points|Lines|Regions)', '', name).strip().lower()
        if name in NAME_MAP:
            name = NAME_MAP[name]
        if name[-1] == 's':
            name = name[:-1]
        return name

    def _load_1d_results(self) -> None:
        node_count = int(self._get_property('Number 1D Nodes'))
        if node_count > 0:
            self.nodes = self._load_nodes()
            relpath = self._get_property('1D Node Maximums')
            if relpath:
                fpath = self.fpath.parent / relpath
                self.nodes.maximums = TPCMaximum(fpath)
            i = self._get_property_index('1D Node Maximums') + 1
            for row in self._df.iloc[i:].itertuples():
                if row[1] == '1D Channel Maximums':
                    break
                elif '1D' not in row[1]:
                    break
                _, name, relpath = row
                name = self._1d_result_name(name)
                fpath = self.fpath.parent / relpath
                self.nodes.load_time_series(name, fpath, index_col=1)

        chan_count = int(self._get_property('Number 1D Channels'))
        if chan_count > 0:
            self.channels = self._load_channels()
            relpath = self._get_property('1D Channel Maximums')
            if relpath:
                fpath = self.fpath.parent / relpath
                self.channels.maximums = TPCMaximum(fpath)
            i = self._get_property_index('1D Channel Maximums') + 1
            for row in self._df.iloc[i:].itertuples():
                if row[1] == '1D Channel Maximums':
                    break
                elif '1D' not in row[1]:
                    break
                _, name, relpath = row
                name = self._1d_result_name(name)
                fpath = self.fpath.parent / relpath
                self.channels.load_time_series(name, fpath, index_col=1)

    def _load_po_results(self) -> None:
        df = self._df[self._df.iloc[:,0].str.contains('2D')]
        for row in df.itertuples():
            if not self.po:
                self.po = TPCPO(None)
            _, name, relpath = row
            name = self._2d_result_name(name)
            fpath = self.fpath.parent / relpath
            self.po.load_time_series(name, fpath, index_col=1)

    def _load_rl_results(self) -> None:
        rl_point_count = self._get_property('Number Reporting Location Points')
        if rl_point_count:
            rl_point_count = int(rl_point_count)
        else:
            rl_point_count = 0
        if rl_point_count:
            df = self._df[self._df.iloc[:,0].str.contains('Reporting Location Points')]
            for row in df.itertuples():
                if 'Number' in row[1]:
                    continue
                if not self.rl:
                    self.rl = TPCRL(None)
                _, name, relpath = row
                name = self._rl_result_name(name)
                fpath = self.fpath.parent / relpath
                if name == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximum(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, index_col=1)

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
                _, name, relpath = row
                name = self._rl_result_name(name)
                fpath = self.fpath.parent / relpath
                if name == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximum(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, index_col=1)

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
                _, name, relpath = row
                name = self._rl_result_name(name)
                fpath = self.fpath.parent / relpath
                if name == 'maximum':
                    if not self.rl.maximums:
                        self.rl.maximums = TPCMaximum(fpath)
                    else:
                        self.rl.maximums.append(fpath)
                else:
                    self.rl.load_time_series(name, fpath, index_col=1)
