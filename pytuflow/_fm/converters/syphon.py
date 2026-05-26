import math

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .qh_control import QHControl


class Syphon(QHControl):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'SYPHON_'

    def calc_qh_matrix(self) -> pd.DataFrame:
        # empty matrix
        matrix = self.empty_matrix()
        # populate matrix
        for i, d2 in enumerate(matrix.index):
            for j, d1 in enumerate(matrix.columns):
                matrix.iloc[i, j] = self.extract_flow(d1, d2, None)
        return matrix

    def empty_matrix(self, *args, **kwargs) -> pd.DataFrame:
        npts = 21
        inc = ((self.unit.zmax - self.unit.zc) * 5) / npts
        depths = [inc * x for x in range(npts + 1)]
        df = pd.DataFrame(np.zeros((len(depths), len(depths))), columns=depths, index=depths)
        df.index.name = 1.
        return df

    def extract_flow(self, d1: float, d2: float, curve: pd.DataFrame) -> float:
        if d1 < d2:
            return 0.
        return self.calc_flow(d1, d2, curve)

    def calc_flow(self, d1: float, d2: float, *args, **kwargs) -> float:
        if np.isclose(d1, 0.) or np.isclose(d1, d2):
            return 0.
        h1 = self.unit.zc + d1
        h2 = self.unit.zc + d2
        if h1 <= self.unit.zsoff and (d2 == 0 or (d1 / d2) > self.unit.m):  # free flow
            q = 0.544 * self.unit.cweir * self.breadth(d1) * np.sqrt(9.8 * d1 ** 1.5)
        elif h1 <= self.unit.zsoff and (d1 / d2) <= self.unit.m:  # drowned weir flow
            drownf = (1 - d2 / d1) / (1 - self.unit.m)
            q = 0.544 * self.unit.cweir * self.breadth(d1) * np.sqrt(9.8 * d1 ** 1.5) * drownf
        elif h1 > self.unit.zsoff and h1 < self.unit.zprime:  # transitional flow
            qblack = 0.799 * self.unit.cfull * self.unit.area * np.sqrt(2 * 9.8) * np.sqrt(self.unit.zprime - h2)
            drownf = (1 - d2 / d1) / (1 - self.unit.m)
            qweir = 0.544 * self.unit.cweir * self.breadth(d1) * np.sqrt(9.8 * d1 ** 1.5) * drownf
            q = d1 * (qblack - qweir) / (self.unit.zprime - self.unit.zsoff) + qweir
        elif h1 >= self.unit.zprime and h1 < self.unit.zmax:  # pipe / blackwater flow
            q = 0.799 * self.unit.cfull * self.unit.area * np.sqrt(2 * 9.8) * np.sqrt(h1 - h2)
        elif h1 > self.unit.zmax and (h2 <= self.unit.zmax or (h1 - self.unit.zmax) / (h2 - self.unit.zmax) > self.unit.m):
            qblack = 0.799 * self.unit.cfull * self.unit.area * np.sqrt(2 * 9.8) * np.sqrt(h1 - h2)
            q = qblack + 0.544 * self.unit.cweir * self.breadth(d1) * np.sqrt(9.8 * (h1 - self.unit.zmax) ** 1.5)
        else:
            qblack = 0.799 * self.unit.cfull * self.unit.area * np.sqrt(2 * 9.8) * np.sqrt(h1 - h2)
            drownf = (1 - (h2 - self.unit.zmax) / (h1 - self.unit.zmax)) / (1 - self.unit.m)
            q = qblack + 0.544 * self.unit.cweir * self.breadth(d1) * np.sqrt(9.8 * (h1 - self.unit.zmax) ** 1.5) * drownf
        return q

    def breadth(self, d1: float) -> float:
        """Breadth of flow of a circular conduit given a depth."""
        return self.unit.area / (self.unit.zmax - self.unit.zc)
