from collections import OrderedDict
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .xs import CrossSection
from .driver import DatabaseDriver
from .river_unit_handler import RiverUnit
from .dat import Dat
from ...tmf_types import PathLike


class FmCrossSection(RiverUnit, CrossSection):

    def __init__(self, *args, **kwargs) -> None:
        super(FmCrossSection, self).__init__(*args, **kwargs)
        self.type = 'RIVER'
        self.col_name_x = 'x'
        self.col_name_z = 'y'
        self.col_name_n = 'n'

    def __repr__(self) -> str:
        if self.name:
            return f'<DatCrossSection {self.name}>'
        return '<DatCrossSection>'

    @property
    def name(self) -> str:
        return self.id

    @name.setter
    def name(self, value: str) -> None:
        self.id = value


class FmCrossSectionDatabaseDriver(DatabaseDriver):
    """Flood Modeller DAT cross-section database driver."""

    def __init__(self) -> None:
        super().__init__()
        self.dat = Dat()
        self.dat.add_handler(FmCrossSection)

    def __repr__(self):
        if self.fpath:
            return f'<FmCrossSectionDatabaseDriver {self.fpath.stem}>'
        return '<FmCrossSectionDatabaseDriver>'

    @staticmethod
    def test_is_dat(path: PathLike) -> bool:
        # docstring inherited
        if Path(path).suffix.lower() == '.dat':
            try:
                with open(path, 'r') as f:
                    for i, line in enumerate(f):
                        if line.startswith('#REVISION#'):
                            return True
                        if i > 10:
                            break
            except Exception:
                pass
        return False

    def name(self) -> str:
        # docstring inherited
        return 'dat_cross_section'

    def load(self, path: PathLike, *args, **kwargs) -> pd.DataFrame:
        """Load the DAT file.

        Parameters
        ----------
        path : PathLike
            The file path to the DAT file.

        Returns
        -------
        pd.DataFrame
            The cross-section data as a DataFrame.
        """
        d = OrderedDict({
            'ID': [],
            'Name': [],
            'Type': []
        })
        self.fpath = Path(path)
        self.dat.load(self.fpath)
        for xs in self.dat.units(FmCrossSection):
            d['ID'].append(xs.uid)
            d['Name'].append(xs.id)
            d['Type'].append(xs.type)
        df = pd.DataFrame(d)
        df.set_index('ID', inplace=True)
        return df

    def cross_sections(self) -> list[FmCrossSection]:
        """no-doc"""
        return self.dat.units(FmCrossSection)

    def unit(self, id_: str, return_only_one: bool = False) -> FmCrossSection:
        """no-doc"""
        unit = self.dat.unit(id_)
        if return_only_one:
            return unit[0] if isinstance(unit, list) else unit
        return unit
