from .gpkg_time_series_result_item import GPKGResultItem
from ..abc.nodes import Nodes


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'total inflow', 'v': 'velocity', 'e': 'energy', 'vol': 'storage volume',
                     'mb': 'mass balance error', 'qa': 'flow area', 'd': 'depth', 'flow': 'total inflow',
                     'total q': 'total inflow', 'total flow': 'total inflow'}


class GPKGNodes(GPKGResultItem, Nodes):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<GPKG TS Node: {self.fpath.stem}>'
        return '<GPKG TS Node>'

    def load(self) -> None:
        pass

    def long_plot_result_types(self) -> list[str]:
        return ['Bed Level', 'Pit Level', 'Pipes'] + self.result_types(None)

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
