import logging
import typing
from pathlib import Path
from typing import Union
from packaging.version import Version

try:
    import pandas as pd
    from pandas.errors import ParserError
except ImportError:
    from ...stubs import pandas as pd
    from ...stubs.pandas.errors import ParserError

from .driver import DatabaseDriver
from ...tfpathlib import TuflowPath
from ...tmf_types import PathLike
from ...utils.text_to_db_parser import text_to_db_parser


logger = logging.getLogger('pytuflow')


class CsvDatabaseDriver(DatabaseDriver):
    """Driver for CSV database files. This class is responsible for parsing CSV files."""

    @staticmethod
    def test_is_csv(path: PathLike) -> bool:
        # docstring inherited
        if '|' in str(path):  # most likely FEWS type
            return False

        path = TuflowPath(path)
        if not path.exists():
            return path.suffix.lower() in ['.csv', '.tsoilf', '.tmf']

        if path.suffix.lower() in ['.csv', '.tsoilf', '.tmf']:
            return True

        if path.suffix.lower() in ['.ts1', '.dss', '.out', '.loc', '.tot']:
            return False

        if TuflowPath(path).is_file_binary():
            return False

        # basic check to see if it is comma-delimited or tab delimited (it should be comma)
        try:
            with path.open() as f:
                while True:
                    line = f.readline()
                    if not line:
                        return False
                    if not line.strip():
                        continue
                    if len(line.split(',')) == 1 and len(line.split('\t')) > 1:
                        return False
                    return True
        except IOError:
            pass

        return False

    def name(self) -> str:
        # docstring inherited
        return 'csv'

    @staticmethod
    def find_header_from_names(path: Path, names: str | list[str]) -> int:
        header_row = 0
        with open(path, 'r') as f:
            for i, line in enumerate(f):
                data = [x.strip() for x in line.split(',')]
                found = True
                if isinstance(names, list):
                    for h in names:
                        if h.strip() not in data:
                            found = False
                    if found:
                        header_row = i
                        break
                elif names.strip() in data:
                    header_row = i
                    break
        return header_row

    def load(self, path: PathLike, header_kwargs: dict[str, typing.Any], index_col: Union[int, bool], remove_comments: bool = True):
        # docstring inherited
        self.fpath = Path(path)
        header = header_kwargs.get('header', None)
        if header == 'infer':
            header_row = 'infer'
        elif isinstance(header, (list, str)) and header and isinstance(header[0], str):
            header_kwargs['header'] = self.find_header_from_names(path, header)
            header_row = header_kwargs['header']
        else:
            header_row = header

        try:
            if remove_comments:
                df = pd.read_csv(path, index_col=index_col, encoding_errors='ignore', comment='!', **header_kwargs)
            elif header_row is not None:
                df = pd.read_csv(path, index_col=index_col, encoding_errors='ignore', **header_kwargs)
            else:
                found = False
                with open(path, 'r') as f:
                    for i, line in enumerate(f):
                        if header_kwargs.get('names') and len([x for x in header_kwargs['names'] if x in line]) == len(header_kwargs['names']):
                            found = True
                            break
                    if found:
                        df = pd.read_csv(f, index_col=index_col, encoding_errors='ignore', **header_kwargs)
                    else:
                        df = pd.read_csv(path, index_col=index_col, encoding_errors='ignore', comment='!', **header_kwargs)
            if header_row == 'infer':
                try:
                    df.columns.astype('f4')
                    df = df.reset_index().T.reset_index().T.set_index(0)
                except (ValueError, TypeError):
                    pass
            # strip strings in object columns
            if Version(pd.__version__) >= Version('3'):
                df.loc[:, df.select_dtypes(include='str').columns] = df.select_dtypes(include='str').map(
                    lambda x: x.strip() if isinstance(x, str) else x)
                col_header_are_strings = df.columns.dtype == 'str'
            else:
                df.loc[:, df.select_dtypes(include='object').columns] = df.select_dtypes(include='object').map(
                    lambda x: x.strip() if isinstance(x, str) else x)
                col_header_are_strings = df.columns.dtype == 'object'
            if col_header_are_strings:
                try:
                    return df.loc[:,~df.columns.str.contains('^Unnamed')]
                except AttributeError:
                    # try without regex
                    return df.loc[:,~df.columns.str.contains('Unnamed', regex=False)]
            return df
        except ParserError:
            # file must be a little nasty - have to do it manually :(
            try:
                return text_to_db_parser(path)
            except Exception:
                logger.error('Failed to parse CVS file at: {}'.format(path))
                raise ParserError(f'Failed to parse CSV file {path}')
