import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlite3 import Cursor


def gpkg_time_series_extractor(cur: 'Cursor', dtype_name: str, table_name: str) -> pd.DataFrame:
    """Extract the time series data from a TUFLOW GeoPackage Time Series file for
    a given data type from a given table.

    The dtype_name, and table_name arguments must match the name of the data type in the
    GeoPackage file exactly (case-sensitive).

    Parameters
    ----------
    cur : sqlite3.Cursor
        The SQLite cursor object for the connected database to extract from.
    dtype_name : str
        The name of the data type to extract.
    table_name : str
        The name of the table to extract the data from.

    Returns
    -------
    pd.DataFrame
        The extracted time series data.

    Examples
    --------
    >>> import sqlite3
    >>> conn = sqlite3.connect('path/to/file.gpkg')
    >>> cur = conn.cursor()
    >>> gpkg_time_series_extractor(cur, 'Water Level', 'EG15_001_TS_1D_P')
    time      FC01.1_R.1  FC01.1_R.2  FC01.2_R.1  ...      Pit6      Pit7      Pit9                                          ...
    0.000000    0.000000    0.000000    0.001610  ...  0.000000  0.000000  0.000000
    0.083333    0.000000    0.000000    0.001610  ...  0.000000  0.000000  0.000000
    0.166667    0.000025    0.000000    0.017934  ...  0.000000  0.000000  0.000000
    0.250000    0.423264    0.096347    0.026454  ...  0.000000  0.000000  0.000000
    0.333333    0.655259    0.399998    0.059989  ...  0.000000  0.000000  0.000000
    ...              ...         ...         ...  ...       ...       ...       ...
    2.666667    0.896279    0.814171    1.726028  ...  0.470355  1.154439  1.479010
    2.750000    0.817359    0.732964    1.634610  ...  0.353785  1.039123  1.367314
    2.833333    0.715444    0.631088    1.555234  ...  0.210500  0.899082  1.229615
    2.916667    0.597825    0.478600    1.458616  ...  0.025982  0.668481  1.007138
    3.000000    0.496117    0.309223    1.378321  ...  0.014117  0.187332  0.191306
    """
    cur.execute(f'SELECT ID, Time_relative, "{dtype_name}" FROM "{table_name}";')
    df = pd.DataFrame(cur.fetchall(), columns=['ID', 'time', dtype_name])
    df = df.pivot(index='time', columns='ID', values=dtype_name)
    df.columns.name = None  # to be consistent with other outputs
    return df
