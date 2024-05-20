from ..tpc.tpc_channels import TPCChannels
from .info_time_series_result_item import INFOResultItem


class INFOChannels(TPCChannels, INFOResultItem):
    """Info Channel class."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<Info Channels: {self.fpath.stem}>'
        return '<Info Channels>'
