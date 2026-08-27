import logging
import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .qh_control import QHControl


logger = logging.getLogger('pytuflow')
formulations = {
            6: lambda x: 0.49 - 0.24 * x - 1.2 * x ** 2 + 2.17 * x ** 3 - 1.03 * x ** 4,
            8: lambda x: 0.49 + 1.08 * x - 5.27 * x ** 2 + 6.79 * x ** 3 - 2.83 * x ** 4,
            12: lambda x: 0.49 + 1.06 * x - 4.43 * x ** 2 + 5.18 * x ** 3 - 1.97 * x ** 4,
            15: lambda x: 0.49 + 1. * x - 3.57 * x ** 2 + 3.82 * x ** 3 - 1.38 * x ** 4,
            18: lambda x: 0.49 + 1.32 * x - 4.13 * x ** 2 + 4.24 * x ** 3 - 1.5 * x ** 4,
            25: lambda x: 0.49 + 1.51 * x - 3.83 * x ** 2 + 3.4 * x ** 3 - 1.05 * x ** 4,
            35: lambda x: 0.49 + 1.69 * x - 4.05 * x ** 2 + 3.62 * x ** 3 - 1.1 * x ** 4,
            90: lambda x: 0.49 + 1.46 * x - 2.56 * x ** 2 + 1.44 * x ** 3
        }


class Labyrinth(QHControl):

    def __init__(self, unit: 'Handler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.alpha = unit.alpha
        else:
            self.alpha = 0

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'LABYRINTH_'

    def calc_qh_matrix(self) -> pd.DataFrame:
        if self.alpha < 6:
            logger.warning(
                f'{self.unit.uid} has an alpha angle less than the lower limit of 6 deg... using 6 deg for weir discharge calculation'
            )
            self.alpha = 6
        elif self.alpha > 90:
            self.alpha = 90
            logger.warning(
                f'{self.unit.uid} has an alpha angle greater than the upper limit of 90 deg... using 90 deg for weir discharge calculation'
            )
        else:
            self.alpha = self.alpha

        # empty matrix
        matrix = self.empty_matrix()
        # populate matrix
        for i, d2 in enumerate(matrix.index):
            for j, d1 in enumerate(matrix.columns):
                matrix.iloc[i, j] = self.extract_flow(d1, d2, None)
        return matrix

    def empty_matrix(self, *args, **kwargs) -> pd.DataFrame:
        npts = 11
        inc = (self.unit.p1 * 0.9) / npts
        depths = [inc * x for x in range(npts + 1)]
        df = pd.DataFrame(np.zeros((len(depths), len(depths))), columns=depths, index=depths)
        df.index.name = 1.
        return df

    def calc_flow(self, d1: float, d2: float, *args, **kwargs) -> float:
        if np.isclose(d1, 0.) or np.isclose(d1, d2):
            return 0.
        cd = self.calc_weir_coef(d1)
        q = 2. / 3. * cd * self.unit.l * np.sqrt(2 * 9.8) * d1 ** (3 / 2)
        if (self.unit.m == 0 and np.isclose(d2, 0)) or (self.unit.m > 0 and d2 < self.unit.m * d1):  # free flow
            drownf = 1.
        else:
            if self.unit.m == 0:
                drownf = (1 - d2 ** (3. / 2.) / d1 ** (3. / 2.)) ** 0.385
            else:
                drownf = ((1 - d2 / d1) / (1 - self.unit.m)) ** 0.5
        return q * drownf * self.unit.ccf

    def calc_weir_coef(self, d1: float) -> float:
        hp = min(0.9, (d1 / self.unit.p1))
        if self.alpha == 90:
            hp = 0.7
        if np.floor(self.unit.alpha) in formulations:
            cd = max(self.unit.cdlim, formulations[np.floor(self.unit.alpha)](hp))
        elif np.ceil(self.unit.alpha) in formulations:
            cd = max(self.unit.cdlim, formulations[np.ceil(self.unit.alpha)](hp))
        else:   # interpolate
            cd_array = np.array([[k, v(hp)] for k, v in formulations.items()])
            cd = np.interp(self.alpha, cd_array[:,0], cd_array[:,1])
        return cd
