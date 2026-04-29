import numpy as np

from .lp_base_provider import LongProfileBaseProvider
from .lp2d_extractor import LP2DExtractor
from .lp_gis_driver import LongProfileGIS
from ..._pytuflow_types import PathLike


class LP2DProvider(LongProfileBaseProvider):

    def __init__(self, fpath: PathLike, gis_fpath: PathLike | None):
        super().__init__(fpath, gis_fpath)
        self.gis_provider = LongProfileGIS(gis_fpath, id_col_name='Label') if gis_fpath else None
        self.provider = LP2DExtractor(fpath, self.gis_provider)
        self.name = self.provider.name
        self.display_name = self.fpath.name
        self.pnt_labels = self.provider.pnt_labels
        self.reference_time = self.provider.reference_time

    def maximum(self) -> np.ndarray:
        return self.provider.maximum()

    def bed_level(self) -> np.ndarray:
        return np.append(self.provider.ch.reshape(-1, 1), self.provider.bed_level().reshape(-1, 1), axis=1)

    def maximum_section(self) -> np.ndarray:
        a = self.maximum()
        return np.append(self.provider.ch.reshape(-1, 1), a[:,[0]], axis=1)
