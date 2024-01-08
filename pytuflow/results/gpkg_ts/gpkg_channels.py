from .gpkg_time_series_result_item import GPKGResultItem
from ..abc.channels import Channels


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'flow', 'v': 'velocity', 'e': 'energy', 'vol': 'channel volume',
                     'channel vol': 'channel volume', 'chan vol': 'channel volume',
                     'qa': 'flow area', 'd': 'channel depth', 'flow': 'total inflow',
                     'total q': 'total inflow', 'total flow': 'total inflow'}


class GPKGChannels(GPKGResultItem, Channels):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<GPKG TS Channel: {self.fpath.stem}>'
        return '<GPKG TS Channel>'

    def load(self) -> None:
        pass

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
