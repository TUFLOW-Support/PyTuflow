import logging
import os
from collections import OrderedDict
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .xs import CrossSection
from .driver import DatabaseDriver
from ...gis import GISAttributes
from ...tmf_types import PathLike
from ...tfpathlib import TuflowPath
from ...tfstrings.patterns import contains_variable


FIELD_NAMES = ['source', 'type', 'flags', 'column_1', 'column_2', 'column_3', 'column_4', 'column_5', 'column_6']


XZ_COL_3_FLAGS = ('R', 'M', 'N')
XZ_COL_4_FLAGS = ('P',)
XZ_COL_5_FLAGS = ('A',)
XZ_COL_6_FLAGS = ('E', 'T')
HW_COL_3_FLAGS = ('A',)
HW_COL_4_FLAGS = ('P',)
HW_COL_5_FLAGS = ('F', 'N')
HW_COL_6_FLAGS = ('E',)


logger = logging.getLogger('pytuflow')


class UnresolvedAttributeError(Exception):
    """Error class to indicate that an attribute contains a wildcard and should be resolved later."""
    pass


class TuflowCrossSection(CrossSection):
    """Class for TUFLOW CSV style cross-section."""

    __slots__ = ('parent_dir', 'attrs', 'source', 'type', 'flags', 'col1', 'col2', 'col3', 'col4', 'col5', 'col6',
                 'col_name_m', 'col_name_r', 'col_name_p', 'col_name_a', 'col_name_e', 'col_name_t', '_cols',
                 'header_row_ind', 'header_col_ind')

    def __new__(cls, parent_dir: PathLike, attrs: dict) -> object:
        attrs_ = {x.lower(): y for x, y in attrs.items()}
        if attrs_.get('type') in ['HW', 'CS']:
            cls = TuflowCrossSectionHW
        elif attrs_.get('type') in ['LC', 'BG']:
            cls = TuflowLossTable
        elif attrs_.get('type') == 'NA':
            cls = TuflowNATable
        return object.__new__(cls)

    def __init__(self, parent_dir: PathLike, attrs: dict) -> None:
        """
        Parameters
        ----------
        parent_dir : PathLike
            The parent directory of the cross-section CSV file.
        attrs : dict
            The cross-section GIS feature attributes
        """
        super().__init__(parent_dir, attrs)
        #: Path: The parent directory of the cross-section CSV file.
        self.parent_dir = Path(parent_dir)
        #: dict: The cross-section GIS feature attributes.
        self.attrs = attrs
        #: str: the source attribute
        self.source = None
        #: str: the type attribute
        self.type = None
        #: list[str]: the flags attributes
        self.flags = []
        #: str: the column 1 attribute
        self.col1 = None
        #: str: the column 2 attribute
        self.col2 = None
        #: str: the column 3 attribute
        self.col3 = None
        #: str: the column 4 attribute
        self.col4 = None
        #: str: the column 5 attribute
        self.col5 = None
        #: str: the column 6 attribute
        self.col6 = None
        #: str: The column name within the dataframe for the mannings M values (if applicable).
        self.col_name_m = None  # mannings M
        #: str: The column name within the dataframe for the relative resistance values (if applicable).
        self.col_name_r = None  # relative resistance
        #: str: The column name within the dataframe for the position values (1, 2, 3) for left bank, mainstream, right bank.
        self.col_name_p = None  # position values (1, 2, 3) for left bank, mainstream, right bank
        #: str: The column name within the dataframe for the addition to raise/lower z values.
        self.col_name_a = None  # addition to raise/lower z values
        #: str: The column name within the dataframe for the effective flow area.
        self.col_name_e = None  # effective flow area
        #: str: The column name within the dataframe for the total flow area.
        self.col_name_t = None  # total flow area
        self._cols = None
        self.header_row_ind = None
        self.header_col_ind = []
        self._load_initial()

    def __repr__(self) -> str:
        if self.name:
            return f'<TuflowCrossSection {self.name}>'
        return '<TuflowCrossSection>'

    @property
    def id(self) -> str:
        if self.col1:
            return f'{self.source}::{self.col1}'
        else:
            return f'{self.source}'

    @id.setter
    def id(self, value: str):
        pass

    @property
    def name(self) -> str:
        #: str: The name of the cross-section (same as the source attribute)
        if self.col1:
            return f'{self.source} ({self.col1})'
        else:
            return self.source

    @name.setter
    def name(self, value: str) -> None:
        self.source = value

    @property
    def m(self) -> list[float]:
        #: list[float]: The mannings M values of the cross-section (if applicable).
        if self.col_name_m is not None and self.col_name_m in self.df.columns:
            return self.df[self.col_name_m].tolist()
        return []

    @property
    def r(self) -> list[float]:
        #: list[float]: The relative resistance values of the cross-section (if applicable).
        if self.col_name_r is not None and self.col_name_r in self.df.columns:
            return self.df[self.col_name_r].tolist()
        return []

    @property
    def p(self) -> list[float]:
        #: list[float]: The position values (1, 2, 3) for left bank, mainstream, right bank.
        if self.col_name_p is not None and self.col_name_p in self.df.columns:
            return self.df[self.col_name_p].tolist()
        return []

    @property
    def a(self) -> list[float]:
        #: list[float]: The addition to raise/lower z values.
        if self.col_name_a is not None and self.col_name_a in self.df.columns:
            return self.df[self.col_name_a].tolist()
        return []

    @property
    def e(self) -> list[float]:
        #: list[float]: The effective flow area.
        if self.col_name_e is not None and self.col_name_e in self.df.columns:
            return self.df[self.col_name_e].tolist()
        return []

    @property
    def t(self) -> list[float]:
        #: list[float]: The total flow area.
        if self.col_name_t is not None and self.col_name_t in self.df.columns:
            return self.df[self.col_name_t].tolist()
        return []

    def _load_initial(self):
        self._parse_attrs()

    def load(self, *args, **kwargs) -> None:
        # docstring inherited
        try:
            self.find_csv_header()
        except FileNotFoundError as e:
            logger.warning(str(e))
            return
        self._load_csv_data()

    @staticmethod
    def _check_for_wildcard(string: str) -> bool:
        return contains_variable(str(string))

    def _parse_attrs(self) -> None:
        attrs = OrderedDict({x.lower(): y for x, y in self.attrs.items()})
        self.source = attrs.get('source')
        if os.name != 'nt' and '\\' in self.source:
            self.source = self.source.replace('\\', '/')
        # if self._check_for_wildcard(self.source):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Source" attribute.')
        if not self.source:
            raise UnresolvedAttributeError('Cross-Section "Source" attribute is required.')
        self.fpath = self.parent_dir / self.source
        # if not self.fpath.exists():
        #     raise FileNotFoundError(f'Cross-Section CSV file not found: {self.fpath}')
        self.type = attrs.get('type')
        # if self._check_for_wildcard(self.type):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Type" attribute.')
        if not self.type:
            raise UnresolvedAttributeError('Cross-Section "Type" attribute is required.')
        self.type = self.type.upper()
        self.flags = attrs.get('flags', '')
        # if self._check_for_wildcard(self.flags):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Flags" attribute.')
        self.flags = [x.strip().upper() for x in self.flags] if self.flags is not None else []
        if self.flags:
            self.flags = [x for x in self.flags]
        self.col1 = attrs.get('column_1')
        # if self._check_for_wildcard(self.col1):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_1" attribute.')
        self.col2 = attrs.get('column_2')
        # if self._check_for_wildcard(self.col2):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_2" attribute.')
        self.col3 = attrs.get('column_3')
        # if self._check_for_wildcard(self.col3):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_3" attribute.')
        self.col4 = attrs.get('column_4')
        # if self._check_for_wildcard(self.col4):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_4" attribute.')
        self.col5 = attrs.get('column_5')
        # if self._check_for_wildcard(self.col5):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_5" attribute.')
        self.col6 = attrs.get('column_6')
        # if self._check_for_wildcard(self.col6):
        #     raise UnresolvedAttributeError('Cannot load cross-section with wildcard in "Column_6" attribute.')
        self._cols = [x.strip().lower() for x in [self.col1, self.col2, self.col3, self.col4, self.col5, self.col6] if x]

    def find_csv_header(self) -> None:
        if not self.fpath.exists():
            if self.source.count('<<') > 0:
                raise FileNotFoundError(f'Cross-Section CSV file not found. Variable in "Source" attribute not resolved: {self.source}')
            raise FileNotFoundError(f'Cross-Section CSV file not found: {self.source}')

        with self.fpath.open() as f:
            data_prev = None
            for i, line in enumerate(f):
                data = [x.strip(' \t\n"\'') for x in line.split(',')]
                data_lower = [x.lower() for x in data]
                if len(data) < 2:
                    continue
                if self._cols:
                    if [x for x in self._cols if x in data_lower]:
                        self.header_row_ind = i
                        self._get_col_inds(i, line, data_lower)
                        for j, subline in enumerate(f):
                            subline_data = [x.strip(' \t\n"\'') for x in subline.split(',')]
                            try:
                                float(subline_data[self.header_col_ind[0]])
                                self.header_row_ind = i + j
                                data = subline_data
                                break
                            except ValueError:
                                continue
                        self._populate_col_names(data)
                        break
                    continue
                try:
                    float(data[0])
                    self.header_row_ind = i - 1
                    self._get_col_inds(i, line, data_lower)
                    self._populate_col_names(data_prev)
                    break
                except (ValueError, TypeError, IndexError):
                    data_prev = data
                    continue
        if self.header_row_ind is None:
            # logging handled by calling function
            raise ValueError(f'Column headers not found in CSV file: {self.fpath}')
        if self.header_row_ind == -1:
            self.header_row_ind = None

    def _populate_col_names_main(self, data: list[str]) -> None:
        """Populates main columns - for XZ this is X and Z. For HW and CS this is Z and W."""
        if not data:  # no header in CSV - use pandas default column names
            self.col_name_x = 0
            self.col_name_z = 1
        else:
            self.col_name_x = data[self.header_col_ind[0]]
            self.col_name_z = data[self.header_col_ind[1]]

    def _populate_col_names(self, data: list[str]) -> None:
        self._populate_col_names_main(data)

        # collect column names based on flags - if errors occur try and persist with the data we have
        col_count = 1
        for i in range(2, 6):
            flag = self._flag_exists(self.type, i)
            if flag:
                col_count += 1
                if len(self.header_col_ind) < col_count + 1:  # +2 because X, Z headers come first
                    self.errors.append(f'Column corresponding to "{flag}" flag not found in CSV file: {self.fpath}')
                else:
                    try:
                        if data:
                            setattr(self, f'col_name_{flag.lower()}', data[self.header_col_ind[i]])
                        else:
                            setattr(self, f'col_name_{flag.lower()}', col_count)
                    except IndexError:
                        self.header_col_ind.remove(i)
                        self.errors.append(f'Column corresponding to "{flag}" flag not found in CSV file: {self.fpath}')

    def _get_col_inds(self, i: int, line: str, data: list[str]) -> None:
        self.header_col_ind.append(self._col_ind(self.col1, 0, i, line, data))
        self.header_col_ind.append(self._col_ind(self.col2, self.header_col_ind[0] + 1, i, line, data))
        if self._flag_exists(self.type, 2):
            self.header_col_ind.append(self._col_ind(self.col3, self.header_col_ind[1] + 1, i, line, data))
        if self._flag_exists(self.type, 3):
            self.header_col_ind.append(self._col_ind(self.col4, self.header_col_ind[2] + 1, i, line, data))
        if self._flag_exists(self.type, 4):
            self.header_col_ind.append(self._col_ind(self.col5, self.header_col_ind[3] + 1, i, line, data))
        if self._flag_exists(self.type, 5):
            self.header_col_ind.append(self._col_ind(self.col6, self.header_col_ind[4] + 1, i, line, data))

    def _col_ind(self, col: str | None, data_index, line_index: int, line: str, data: list[str]) -> int:
        if col:
            try:
                return data.index(col.strip().lower())
            except ValueError:  # choose not to fail here and try and persist with the data we have
                self.errors.append(f'Column header "{col}" not found in CSV file line [{line_index}]: {line}')
                return data_index
        else:
            return data_index

    def _flag_exists(self, type_: str, data_index: int) -> str:
        col_flags = ((), (), (), (), (), ())
        if type_ == 'XZ':
            col_flags = ((), (), XZ_COL_3_FLAGS, XZ_COL_4_FLAGS, XZ_COL_5_FLAGS, XZ_COL_6_FLAGS)
        elif type_ == 'HW' or type_ == 'CS':
            col_flags = ((), (), HW_COL_3_FLAGS, HW_COL_4_FLAGS, HW_COL_5_FLAGS, HW_COL_6_FLAGS)
        flags = [x for x in self.flags if x in col_flags[data_index]]
        if flags:
            return flags[0]
        return ''

    def _load_csv_data(self) -> None:
        try:
            self.df = pd.read_csv(self.fpath, header=self.header_row_ind,
                                  usecols=self.header_col_ind, skip_blank_lines=False)
            blank_df = self.df.loc[self.df.isnull().all(axis=1)]
            if len(blank_df) > 0:
                first_blank_index = blank_df.index[0]
                self.df = self.df[:first_blank_index]
                try:
                    self.df = self.df.astype(np.dtype('float64'))
                except Exception as e:
                    logger.warning(f'Error converting cross-section data to float: {self.fpath}\n{e}')
        except Exception as e:
            # logging handled by calling function
            raise Exception(f'Error reading Cross-Section CSV file: {self.fpath}\n{e}')


class TuflowCrossSectionHW(TuflowCrossSection):
    """Class for TUFLOW CSV 'HW' cross-sections."""

    __slots__ = ('col_name_w', 'col_name_f')

    def __init__(self, parent_dir: PathLike, attrs: dict) -> None:
        # docstring inherited
        super().__init__(parent_dir, attrs)
        #: str: The column name within the dataframe for the flow width.
        self.col_name_w = None  # flow width
        #: str: The column name within the dataframe for the mannings factor.
        self.col_name_f = None  # mannings factor

    def __repr__(self) -> str:
        if self.name:
            return f'<TuflowCrossSectionHW {self.name}>'
        return '<TuflowCrossSectionHW>'

    @property
    def w(self) -> list[float]:
        #: list[float]: The flow width values of the cross-section.
        if self.col_name_w is not None and self.col_name_w in self.df.columns:
            return self.df[self.col_name_w].tolist()
        return []

    @property
    def f(self) -> list[float]:
        #: list[float]: The mannings factor values of the cross-section.
        if self.col_name_f is not None and self.col_name_f in self.df.columns:
            return self.df[self.col_name_f].tolist()
        return []

    def _populate_col_names_main(self, data: list[str]) -> None:
        if not data:  # no header in CSV - use pandas default column names
            self.col_name_z = 0
            self.col_name_w = 1
        else:
            self.col_name_z = data[self.header_col_ind[0]]
            self.col_name_w = data[self.header_col_ind[1]]


class TuflowLossTable(TuflowCrossSection):
    """Class for TUFLOW 'LC' or 'BG' loss tables."""

    def __init__(self, parent_dir: PathLike, attrs: dict) -> None:
        super().__init__(parent_dir, attrs)
        #: str: The column name within the dataframe for the form loss values.
        self.col_name_form_loss = None

    def __repr__(self) -> str:
        if self.name:
            return f'<TuflowLossTable {self.name}>'
        return '<TuflowLossTable>'

    @property
    def lc(self) -> list[float]:
        #: list[float]: The form loss values of the cross-section.
        if self.col_name_form_loss is not None and self.col_name_form_loss in self.df.columns:
            return self.df[self.col_name_form_loss].tolist()
        return []

    def _populate_col_names(self, data: list[str]) -> None:
        if not data:  # no header in CSV - use pandas default column names
            self.col_name_z = 0
            self.col_name_form_loss = 1
        else:
            self.col_name_z = data[self.header_col_ind[0]]
            self.col_name_form_loss = data[self.header_col_ind[1]]


class TuflowNATable(TuflowCrossSection):
    """Class for TUFLOW 'NA' tables."""

    def __repr__(self) -> str:
        if self.name:
            return f'<TuflowNATable {self.name}>'
        return '<TuflowNATable>'

    def _populate_col_names(self, data: list[str]) -> None:
        if not data:  # no header in CSV - use pandas default column names
            self.col_name_z = 0
            self.col_name_a = 1
        else:
            self.col_name_z = data[self.header_col_ind[0]]
            self.col_name_a = data[self.header_col_ind[1]]


class TuflowCrossSectionDatabaseDriver(DatabaseDriver):

    def load(self, path: PathLike, *args, **kwargs) -> pd.DataFrame:
        self.fpath = TuflowPath(path)
        d = OrderedDict({'ID': [], 'Source': [], 'Type': [], 'Flags': [], 'Column_1': [], 'Column_2': [],
                         'Column_3': [], 'Column_4': [], 'Column_5': [], 'Column_6': []})
        for attr in GISAttributes(self.fpath):
            xs = TuflowCrossSection(self.fpath.parent, attr)
            if xs.id in d:
                continue
            d['ID'].append(xs.id)
            d['Source'].append(xs.source)
            d['Type'].append(xs.type)
            d['Flags'].append(', '.join(xs.flags))
            d['Column_1'].append(xs.col1)
            d['Column_2'].append(xs.col2)
            d['Column_3'].append(xs.col3)
            d['Column_4'].append(xs.col4)
            d['Column_5'].append(xs.col5)
            d['Column_6'].append(xs.col6)

        df = pd.DataFrame(d)
        df.set_index('ID', inplace=True)
        return df

    def name(self) -> str:
        return 'tuflow_cross_section'

    @staticmethod
    def test_is_tf_xs(fpath: Path) -> bool:
        # docstring inherited
        if TuflowPath(fpath).suffix.lower() in ['.shp', '.mif', '.gpkg']:
            for attr in GISAttributes(fpath):
                field_names = [x.lower() for x in attr.keys()]
                if field_names[:len(FIELD_NAMES)] == FIELD_NAMES:
                    return True
                break
        return False
