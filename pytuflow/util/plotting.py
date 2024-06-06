from collections import OrderedDict

import pandas as pd


def long_plot_pipes(df: pd.DataFrame) -> OrderedDict:
    """Takes the DataFrame from TPC.long_plot and returns a dictionary of culverts.

    The DataFrame must have the following columns:

    * Channel
    * Offset
    * Bed Level
    * Pipe Obvert

    The function returns a dictionary of DataFrames, where each DataFrame represents a culvert that can
    be passed into a matplotlib.patches.Polygon object.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from TPC.long_plot

    Returns
    -------
    OrderedDict
        Dictionary of DataFrames representing culverts.
    """
    if 'Offset' not in df.columns:
        raise ValueError('Offset not found in DataFrame')
    if 'Bed Level' not in df.columns:
        raise ValueError('Bed Level not found in DataFrame')
    if 'Pipe Obvert' not in df.columns:
        raise ValueError('Pipe Obvert not found in DataFrame')
    if 'Channel' not in df.columns:
        raise ValueError('Channel not found in DataFrame')
    df_shifted = df[['Offset', 'Bed Level', 'Pipe Obvert']].shift(-1).iloc[:-1]
    df1 = df[['Channel', 'Offset', 'Bed Level', 'Pipe Obvert']].iloc[:-1]
    df1 = pd.concat([df1.reset_index(drop=True), df_shifted.reset_index(drop=True)], axis=1)
    d = OrderedDict({
        df1.iloc[i,0]: pd.DataFrame(OrderedDict({
            'x': [df1.iloc[i,1], df1.iloc[i,4], df1.iloc[i,4], df1.iloc[i,1]],
            'y': [df1.iloc[i,2], df1.iloc[i,5], df1.iloc[i,6], df1.iloc[i,3]]
        })) for i in range(0,df1.shape[0],2)
    })
    return d

