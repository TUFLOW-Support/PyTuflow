from datetime import datetime, timedelta

import pandas as pd
from typing import TYPE_CHECKING

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.util.misc_tools import flatten

if TYPE_CHECKING:
    from sqlite3 import Cursor


def time_series_extractor(data_types: list[str], custom_names: list[str], time_series_data: dict,
                          ctx: pd.DataFrame, time_fmt: str, share_idx: bool, reference_time: datetime) -> pd.DataFrame:
    """Extracts time-series data from a dictionary of time-series data. Helper method that can be accessed by all
    time-series output classes.

    Parameters
    ----------
    data_types : list[str]
        The list of data types to extract.
    custom_names : list[str]
        The list of custom names for the data types.
    time_series_data : dict
        The dictionary of time-series data.
    ctx : pd.DataFrame
        The context DataFrame.
    time_fmt : str
        The time format.
    share_idx : bool
        Whether to share the index.
    reference_time : datetime
        The reference time.

    Returns
    -------
    pd.DataFrame
        The extracted time-series data.
    """
    df = pd.DataFrame()
    for dtype2 in data_types:
        dtype = [x for x in custom_names if get_standard_data_type_name(x) == dtype2]
        dtype = dtype[0] if dtype else dtype2
        if dtype2 not in time_series_data:
            continue
        for res_df in time_series_data[dtype2]:
            idx = res_df.columns[res_df.columns.isin(ctx['id'])]
            if idx.empty:
                continue
            df1 = res_df.loc[:, idx]
            if time_fmt == 'absolute':
                df1.index = [reference_time + timedelta(hours=x) for x in df1.index]
            df1.index.name = 'time'
            index_name = df1.index.name
            if not share_idx:
                col_names = flatten([index_name, x] for x in df1.columns)
                df1.reset_index(inplace=True, drop=False)
                df1 = df1[col_names]

            df1.columns = [f'{x}/{dtype}/{df1.columns[i+1]}' if x == index_name else f'{dtype}/{x}' for i, x in enumerate(df1.columns)]
            df = df1 if df.empty else pd.concat([df, df1], axis=1)

    return df


def maximum_extractor(data_types: list[str], custom_names: list[str], maximum_data: dict,
                      ctx: pd.DataFrame, time_fmt: str, reference_time: datetime) -> pd.DataFrame:
    """Extracts maximum data from a dictionary of maximum data. Helper method that can be accessed by all
    time-series output classes.

    Parameters
    ----------
    data_types : list[str]
        The list of data types to extract.
    custom_names : list[str]
        The list of custom names for the data types.
    maximum_data : dict
        The dictionary of maximum data.
    ctx : pd.DataFrame
        The context DataFrame.
    time_fmt : str
        The time format.
    reference_time : datetime
        The reference time.

    Returns
    -------
    pd.DataFrame
        The extracted maximum data.
    """
    df = pd.DataFrame()
    for dtype2 in data_types:
        dtype = [x for x in custom_names if get_standard_data_type_name(x) == dtype2]
        dtype = dtype[0] if dtype else dtype2
        if dtype2 not in maximum_data:
            continue
        for res_df in maximum_data[dtype2]:
            rows = res_df.index[res_df.index.isin(ctx['id'])]
            df1 = res_df.loc[rows]
            if time_fmt == 'absolute':
                df1['tmax'] = df1['tmax'].apply(lambda x: reference_time + timedelta(hours=x))
            df1.columns = [f'{dtype}/{x}' for x in df1.columns]
            if df.empty:
                df = df1
            else:
                df = pd.concat([df, df1], axis=1)
    return df


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
