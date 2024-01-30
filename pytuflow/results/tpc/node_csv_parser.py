from pathlib import Path
from os import PathLike

import numpy as np
import pandas as pd


def parse_node_csv(fpath: PathLike) -> pd.DataFrame:
    """
    Returns 1d_Node.csv as dataframe
    - requires custom parsing due to last column which is a list of connected channels with same delim.
    """
    DTYPE_MAP = [int, str, float, float, int]
    p = Path(fpath)
    with p.open() as f:
        header = [x.strip() for x in f.readline().split(',')]
        data = [[y for y in x.split(',')] for x in f.read().split('\n')]
    for j, row in enumerate(data):
        if not data or not row[0]:
            data.pop(j)
            break
        for i, val in enumerate(row):
            if i < len(DTYPE_MAP):
                try:
                    row[i] = DTYPE_MAP[i](val.strip(' "\'\n\t'))
                except ValueError:
                    row[i] = np.nan
            else:
                row[i] = [x.strip(' "\'\n\t') for x in row[i:]]
                break
        data[j] = row[:6]
    df = pd.DataFrame(data, columns=header)
    df.set_index('Node', inplace=True)
    return df
