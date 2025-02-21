import json
from pathlib import Path
from collections import OrderedDict
from typing import Union

import pandas as pd

from .map_output import MapOutput, PointLocation, LineStringLocation
from .mesh import Mesh
from .._pytuflow_types import PathLike, TimeLike
from .helpers.catch_providers import CATCHProvider


class CATCHJson(MapOutput):

    def __init__(self, fpath: PathLike | str):
        super().__init__(fpath)
        self._fpath = Path(fpath)
        self._data = {}
        self._providers = OrderedDict()
        self._idx_provider = None
        self._load_json(fpath)
        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return True

    @staticmethod
    def _looks_empty(fpath: Path) -> bool:
        return False

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        pass

    def data_types(self, filter_by: str = None) -> list[str]:
        pass

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', averaging_method: str = None) -> pd.DataFrame:
        pass

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, averaging_method: str = None) -> pd.DataFrame:
        pass

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        pass

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, interpolation: str = 'stepped') -> pd.DataFrame:
        pass

    def _load_json(self, fpath: PathLike | str):
        if Path(fpath).is_file():
            with Path(fpath).open() as f:
                self._data = json.load(f, object_pairs_hook=OrderedDict)
        else:
            self._data = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(fpath)

    def _initial_load(self):
        self.name = self._data.get('name')
        default_time_string = 'hours since 1990-01-01 00:00:00'
        self.reference_time, _ = self._parse_time_units_string(self._data.get('time units', default_time_string),
                                                        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                                                        '%Y-%m-%d %H:%M:%S')
        self.units = self._data.get('units', 'metric')
        self._outputs = self._data.get('output data', {})
        self._result_types = [Mesh._get_standard_data_type_name(x) for x in self._data.get('result types')]

        index_result_name = self._data.get('index')
        for res_name, output in self._outputs.items():
            provider = CATCHProvider.from_catch_json_output(self._fpath.parent, output)
            if res_name == index_result_name:
                self._idx_provider = provider
            self._providers[res_name] = provider

        self._load_info()

    def _load_info(self):
        self._info = pd.DataFrame(columns=['data_type', 'type', 'is_max', 'is_min', 'static', 'start', 'end', 'dt'])
        for provider in self._providers.values():
            if provider == self._idx_provider:
                continue
            if provider.reference_time != self.reference_time:
                provider.offset_time = (provider.reference_time - self.reference_time).total_seconds()
            df = provider.info_with_correct_times()
            self._info = pd.concat([self._info, df], axis=0) if not self._info.empty else df

        self._info = self._info.drop_duplicates()
