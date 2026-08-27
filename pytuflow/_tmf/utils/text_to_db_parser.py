import logging
import re
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd
from ..tmf_types import PathLike



logger = logging.getLogger('pytuflow')


def text_to_db_parser(fpath: PathLike) -> pd.DataFrame:
    """
    Parse a text file manually into a pandas DataFrame. Assume comma delimited.

    Don't attempt to assume or read any headers/column names.
    Also don't try and capture any trailing comments, too hard with TUFLOW's free form approach and this has
    probably failed to parse in pandas if this routine is being used, so keep it simple!
    """
    fltregex = re.compile(r'\d+\.\d*')
    intregex = re.compile(r'\d+')
    rows = []
    with open(fpath, 'r') as f:
        for line in f:
            if '!' in line:
                line, _ = line.split('!', 1)
            line = line.strip()
            if not line:
                continue
            row = [x.strip() for x in line.split(',')]
            for i, x in enumerate(row[:]):
                if fltregex.match(x):
                    try:
                        # noinspection PyTypeChecker
                        row[i] = float(x)
                    except ValueError:
                        pass
                elif intregex.match(x):
                    try:
                        # noinspection PyTypeChecker
                        row[i] = int(x)
                    except ValueError:
                        pass
            rows.append(row)
    df = pd.DataFrame(rows)
    return df.set_index(df.columns[0])
