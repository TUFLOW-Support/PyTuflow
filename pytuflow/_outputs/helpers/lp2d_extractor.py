import numpy as np
import pandas as pd

from .lp_data_extractor import LongProfileDataExtractor
from ..._pytuflow_types import PathLike, TimeLike

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .lp_gis_driver import LongProfileGIS

from ...util import pytuflow_logging
logger = pytuflow_logging.get_logger()


class LP2DExtractor(LongProfileDataExtractor):

    def __init__(self, fpath: PathLike, gis_provider: 'LongProfileGIS' = None, **kwargs):
        super().__init__(fpath, **kwargs)
        self.gis_provider = gis_provider
        self.name = '_'.join(self.path.stem.split('_')[:-1])
        self.pnt_labels = []
        self.df = pd.DataFrame()
        self.times = np.empty(0)
        self.ch = np.empty(0)
        self.start_time_col_index = 8  # default value - checked later
        self.load()

    def is_valid(self) -> bool:
        return self.df.shape[0] > 0

    def load(self):
        self.df = pd.read_csv(self.path)
        self.start_time_col_index = self._first_time_col_index(self.df.columns)
        self.times = self.df.columns[self.start_time_col_index:].astype(float).to_numpy()
        self.ch = self.df['Distance'].astype(float).to_numpy()
        if self.gis_provider:
            labels = list(self.gis_provider.feats.keys())
            # sort labels by label length so that the longest is first
            sorted_labels = sorted(labels, key=lambda x: len(x), reverse=True)
            # match label to name and return the first match
            label = None
            for lab in sorted_labels:
                if lab.lower() in self.name.lower():
                    label = lab
                    break
            if label is None:
                logger.warning(f'Could not find label for {self.name} in GIS file - defaulting to {self.name}')
                label = self.name
        else:
            label = self.name
        # results are loaded per CSV (or grouped CSV by result type, so still only one location)
        self.labels = [label]
        self.pnt_labels = [f'{label}_{x:.2f}_pnt{i}' for i, x in enumerate(self.ch)]

    def number_of_points(self) -> int:
        return self.df.shape[0]

    def get_chainages(self, label: str) -> list[float]:
        return self.ch.tolist()

    def get_section(self, label: str, time: TimeLike) -> np.ndarray:
        idx = self._get_closest_timestep_index(time) + self.start_time_col_index
        return np.append(self.ch.reshape(-1, 1), self.df.iloc[:,idx].astype(float).to_numpy().reshape(-1, 1), axis=1)

    def get_time_series(self, label: str, point_ind: int, time_fmt: str) -> np.ndarray:
        data = self.df.iloc[point_ind,self.start_time_col_index:].to_numpy().T
        return np.append(self.times.reshape(-1, 1), data.reshape(-1, 1), axis=1)

    def get_time_series_data_raw(self, label: str) -> np.ndarray:
        return self.df.iloc[:,self.start_time_col_index:].to_numpy().T

    def bed_level(self) -> np.ndarray:
        return self.df['Ground Level'].astype(float).to_numpy()

    def maximum(self) -> np.ndarray:
        return self.df[['Maximum', 'Time of Maximum']].astype(float).to_numpy()

    def minimum(self) -> np.ndarray:
        return self.df[['Minimum', 'Time of Minimum']].astype(float).to_numpy()

    def _get_timesteps(self) -> np.ndarray:
        return self.times

    def _first_time_col_index(self, cols: list | pd.Index) -> int:
        float_cols = set()
        for i, col in enumerate(cols):
            try:
                float(col)
                float_cols.add(i)
                break
            except ValueError:
                continue
        if not float_cols:
            logger.warning('Could not determine first time column index - no columns could be converted to float. Defaulting to 8.')
            return self.start_time_col_index
        return min(float_cols)

