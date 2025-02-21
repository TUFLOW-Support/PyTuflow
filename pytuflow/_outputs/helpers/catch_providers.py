from datetime import datetime
from pathlib import Path

import pandas as pd

from ..xmdf import XMDF
from ..nc_mesh import NCMesh


class CATCHProvider:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.time_offset = 0  # seconds

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProvider':
        if data.get('format').lower() == 'xmdf':
            return CATCHProviderXMDF.from_catch_json_output(parent_dir, data)
        if data.get('format').lower() == 'netcdf mesh':
            return CATCHProviderNCMesh.from_catch_json_output(parent_dir, data)
        raise ValueError('Unknown format: {0}'.format(data.get('format')))

    def info_with_correct_times(self) -> pd.DataFrame:
        df = self._info.copy()
        if not self.time_offset:
            return df
        df['start'] = df['start'].apply(lambda x: x + self.time_offset / 3600.)
        df['end'] = df['end'].apply(lambda x: x + self.time_offset / 3600.)
        for idx, row in df.iterrows():
            if isinstance(row['dt'], tuple):
                df.at[idx, 'dt'] = (row['dt'][0], row['dt'][1] + self.time_offset / 3600.)
        return df


class CATCHProviderXMDF(XMDF, CATCHProvider):

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProviderXMDF':
        p = (parent_dir / data.get('path')).resolve()
        twodm = (parent_dir / data.get('2dm')).resolve()
        return CATCHProviderXMDF(p, twodm=twodm)


class CATCHProviderNCMesh(NCMesh, CATCHProvider):

    @staticmethod
    def from_catch_json_output(parent_dir: Path, data: dict) -> 'CATCHProviderNCMesh':
        p = (parent_dir / data.get('path')).resolve()
        return CATCHProviderNCMesh(p)
