from ..tpc.tpc import TPC
from .info_channels import InfoChannels
from .info_nodes import InfoNodes
from .info_time_series_result_item import InfoResultItem


class Info(TPC):

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
