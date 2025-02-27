from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd

from ..xmdf import XMDF
from ..nc_mesh import NCMesh
from ..map_output import MapOutput, PointLocation, LineStringLocation
from ..._pytuflow_types import TimeLike


class CATCHProvider:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_offset = 0  # seconds
        self._reference_time = None

    @property
    def reference_time(self) -> datetime:
        if self._soft_load_driver.valid:
            driver = self._soft_load_driver
        else:
            self._driver.load()
            self._loaded = True
            driver = self._driver
        return driver.reference_time

    @reference_time.setter
    def reference_time(self, ref_time: datetime):
        if hasattr(self, '_soft_load_driver') and self._soft_load_driver.valid:
            self._soft_load_driver.reference_time = ref_time
        if hasattr(self, '_loaded') and self._loaded:
            self._driver.reference_time = ref_time
        if hasattr(self, '_loaded') and hasattr(self, '_soft_load_driver'):
            self._reference_time = ref_time

    @property
    def has_inherent_reference_time(self) -> bool:
        if self._soft_load_driver.valid:
            driver = self._soft_load_driver
        else:
            self._driver.load()
            self._loaded = True
            driver = self._driver
        return driver.has_inherent_reference_time

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProvider':
        if data.get('format').lower() == 'xmdf':
            return CATCHProviderXMDF.from_catch_json_output(parent_dir, data)
        if data.get('format').lower() == 'netcdf mesh':
            return CATCHProviderNCMesh.from_catch_json_output(parent_dir, data)
        raise ValueError('Unknown format: {0}'.format(data.get('format')))

    def info_with_corrected_times(self) -> pd.DataFrame:
        df = self._info.copy()
        if not self.time_offset:
            return df
        df.loc[~df['static'], 'start'] = df.loc[~df['static'], 'start'] + self.time_offset / 3600.
        df.loc[~df['static'], 'end'] = df.loc[~df['static'], 'end'] + self.time_offset / 3600.
        for idx, row in df.iterrows():
            if isinstance(row['dt'], tuple):
                df.at[idx, 'dt'] = (row['dt'][0], row['dt'][1] + self.time_offset / 3600.)
        return df

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', averaging_method: str = None) -> pd.DataFrame:
        # override - output relative times may need to be adjusted to CATCH reference time
        df = super().time_series(locations, data_types, time_fmt, averaging_method)
        if time_fmt == 'absolute' or not self.time_offset:
           return df
        df.index = df.index + self.time_offset / 3600.
        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, averaging_method: str = None) -> pd.DataFrame:
        # override - input time may need to be offset back to the provider's reference time
        if isinstance(time, (float, int)) and self.time_offset:
            time -= self.time_offset / 3600.
        return super().section(locations, data_types, time, averaging_method)

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        # override - input time may need to be offset back to the provider's reference time
        if isinstance(time, (float, int)) and self.time_offset:
            time -= self.time_offset / 3600.
        return super().curtain(locations, data_types, time)

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, interpolation: str = 'stepped') -> pd.DataFrame:
        # override - input time may need to be offset back to the provider's reference time
        if isinstance(time, (float, int)) and self.time_offset:
            time -= self.time_offset / 3600.
        return super().profile(locations, data_types, time, interpolation)

    def _load(self):
        super()._load()
        if self._reference_time:
            self._driver.reference_time = self._reference_time


class CATCHProviderXMDF(CATCHProvider, XMDF):

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProviderXMDF':
        p = (parent_dir / data.get('path')).resolve()
        twodm = (parent_dir / data.get('2dm')).resolve()
        return CATCHProviderXMDF(p, twodm=twodm)


class CATCHProviderNCMesh(CATCHProvider, NCMesh):

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProviderNCMesh':
        p = (parent_dir / data.get('path')).resolve()
        return CATCHProviderNCMesh(p)
