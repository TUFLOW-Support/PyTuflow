from ..tpc.tpc_channels import TPCChannels
from .info_time_series_result_item import InfoResultItem


class InfoChannels(TPCChannels, InfoResultItem):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<Info Channels: {self.fpath.stem}>'
        return '<Info Channels>'
