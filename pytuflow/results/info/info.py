from pathlib import Path

import pandas as pd

from ..tpc.tpc import TPC
from .info_channels import InfoChannels
from .info_nodes import InfoNodes
from .info_time_series_result_item import InfoResultItem


class Info(TPC):
    """Class for reading TUFLOW info time series results (.info). These are text files with a '.info' extension
    (not '.2dm.info') that are output by the 2013 TUFLOW release. The format is similar to the TPC format, however
    does not include 2D or RL results.
    """

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        # docstring inherited
        if fpath.suffix.upper() != '.INFO':
            return False
        try:
            with fpath.open() as f:
                line = f.readline()
                if not line.startswith('Format Version == 1'):
                    return False
        except Exception as e:
            return False
        return True

    def looks_empty(self, fpath: Path) -> bool:
        # docstring inherited
        TARGET_LINE_COUNT = 10  # fairly arbitrary
        try:
            df = pd.read_csv(self.fpath, sep=' == ', engine='python', header=None)
            if df.shape[0] < TARGET_LINE_COUNT:
                return True
            if df.shape[1] < 2:
                return True
            node_count = int(df[df.iloc[:, 0] == 'Number Nodes'].iloc[0, 1])
            channel_count = int(df[df.iloc[:, 0] == 'Number Channels'].iloc[0, 1])
            if node_count + channel_count == 0:
                return True
            return False
        except Exception as e:
            return True

    def _load_1d_results(self) -> None:
        node_count = int(self._get_property('Number Nodes'))
        if node_count:
            self.nodes = self._load_nodes()
            for res_type in ['Water Levels']:
                relpath = self._get_property(res_type)
                res_type = self._1d_result_name(res_type)
                self._load_result(self.nodes, res_type, relpath)

        channel_count = int(self._get_property('Number Channels'))
        if channel_count:
            self.channels = self._load_channels()
            for res_type in ['Flows', 'Velocities']:
                relpath = self._get_property(res_type)
                res_type = self._1d_result_name(res_type)
                self._load_result(self.channels, res_type, relpath)

    def _load_po_results(self) -> None:
        self.po = None

    def _load_rl_results(self) -> None:
        self.rl = None

    def _load_nodes(self) -> InfoNodes:
        relpath = self._get_property('Node Info')
        relpath = relpath.replace('_1d_','_1d_1d_')
        node_info = self.fpath.parent / relpath
        return InfoNodes(node_info)

    def _load_channels(self) -> InfoChannels:
        relpath = self._get_property('Channel Info')
        relpath = relpath.replace('_1d_','_1d_1d_')
        chan_info = self.fpath.parent / relpath
        return InfoChannels(chan_info)

    def _load_result(self, cls: InfoResultItem, result_type: str, relpath: str) -> None:
        p = self.fpath.parent / relpath
        cls.load_time_series(result_type, p, self.reference_time, 1, result_type)
