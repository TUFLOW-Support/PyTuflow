from collections.abc import Sequence
from pathlib import Path

import numpy as np

try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

from .lp_base import LongProfileBase
from .helpers.lp2d_provider import LP2DProvider
from .helpers.lp_gis_driver import LongProfileGIS
from .._pytuflow_types import PathLike, TimeLike, TuflowPath


class LP2D(LongProfileBase):
    """Class for handling results from the ``2d_lp`` output from TUFLOW Classic/HPC. The class supports
    :meth:`section()<pytuflow.LP2D.section>` extraction along the line. Points are automatically created at each
    distance value in the CSV, enabling :meth:`time_series()<pytuflow.LP2D.time_series>` extraction at
    specific chainage locations.

    The output can be initialised with any number of ``2d_lp`` output files, including files for multiple locations
    (line labels) and data types. TUFLOW writes a CSV file for each location and for each data type. Additional CSV
    files can be added after initialisation with :meth:`add_csv()<pytuflow.LP2D.add_csv>`.

    The GIS file (the ``2d_lp`` input that generated the output) can be optionally provided. In this case
    "Label" attribute field will be used, otherwise the file name excluding the result type will be used as the
    line label. It also provides spatial coordinates for both the line and the generated points.

    Parameters
    ----------
    fpath : PathLike | Sequence[PathLike]
        The CSV file path(s) to the 2d_lp output CSV file(s). Files can be for different locations
        (line labels) and different data types. The data type and the line label
        will be determined from the file name.
    gis_fpath : PathLike, optional
        The file path to the GIS file that corresponds to the ``2d_lp`` output. This is optional, but if not
        provided the class won't be able to determine the line label from the CSV file. It can also provide
        a spatial location for the line and the created points.
    dt_decimal_places : int, optional
        Sets the number of decimal places the delta timestep (dt) is rounded to.
        The (lack of) precision in the timesteps reported in the result CSV files can lead to incorrect dt 
        being calculated by PyTUFLOW. This setting can counter dt miscalculation by rounding the result.

    Examples
    --------
    Loading a result and extracting the maximum profile:

    >>> from pytuflow import LP2D
    >>> import matplotlib.pyplot as plt
    >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
    >>> df = lp.section('model_LP_NAME', ['bed level', 'max h'], -1)  # time can be a dummy value for static results
    >>> df
       offset  branch_id     node_string  bed level   max h
    0    2.07          0  EG02_012_LP_01     44.277  49.863
    1    8.31          0  EG02_012_LP_01     44.150  49.861
    2   14.55          0  EG02_012_LP_01     44.192  49.874
    3   20.79          0  EG02_012_LP_01     48.128  49.149
    4   27.03          0  EG02_012_LP_01     44.007  46.415
    5   33.28          0  EG02_012_LP_01     43.918  47.091
    6   39.52          0  EG02_012_LP_01     43.837  47.095
    7   45.77          0  EG02_012_LP_01     43.866  47.073
    8   52.02          0  EG02_012_LP_01     43.770  47.041
    >>> df.plot(y=['bed level', 'max h'])
    >>> plt.show()

    .. image:: ../assets/images/lp2d_simple_figure.png

    The below is a script that will generate a water level profile plot that has an interactive slider
    that will dynamically update the water level based on the time.

    .. code-block:: python

        from pytuflow import LP2D
        from matplotlib.widgets import Slider


        # Result location - update accordingly
        RESULT = '/path/to/model_LP_NAME_H.csv'

        # initialise subplots
        fig, ax = plt.subplots()

        # initialise the LP2D class and initialise
        # the section dataframe for the first time step
        res = pytuflow.LP2D(RESULT)
        df = res.section(res.name, ['bed level', 'h', 'max h'], 0)

        # generate plot lines
        z_line, = ax.plot(
            df['offset'],
            df['bed level'],
            label='bed level',
            color='black'
        )
        h_line, = ax.plot(
            df['offset'],
            df['h'],
            label='h',
            color='blue'
        )
        max_h_line, = ax.plot(
            df['offset'],
            df['max h'],
            label='max h',
            color='blue',
            linestyle='dashed'
        )

        # plot house-keeping
        ax.legend()
        ax.grid()
        ax.set_xlabel('Distance')
        ax.set_ylabel('Elevation')

        # adjust the main plot to make room for the sliders
        fig.subplots_adjust(bottom=0.25)

        # Make a horizontal slider to control the time
        time_ax = fig.add_axes([0.25, 0.1, 0.65, 0.03])
        time_slider = Slider(
            ax=time_ax,
            label='Time',
            valmin=res.times()[0],
            valmax=res.times()[-1],
            valstep=res.times()[1] - res.times()[0],
            valinit=res.times()[0],
        )

        # callback that updates and extracts water level data
        def time_updated(time_val):
            df = res.section(res.name, 'h', time_val)
            h_line.set_ydata(df['h'])
            fig.canvas.draw_idle()

        # register the update function
        time_slider.on_changed(time_updated)

        plt.show()

    .. video:: ../_static/videos/lp2d_time_slider_example.mp4
        :width: 720
    """

    def __init__(self, fpath: PathLike | Sequence[PathLike], gis_fpath: PathLike = None, dt_decimal_places: int = 0):
        if isinstance(fpath, (str, Path)):
            fpath = [fpath]
        self._csv_fpaths = [Path(x) for x in fpath]
        super().__init__(*self._csv_fpaths)
        self.fpath = TuflowPath(gis_fpath) if gis_fpath is not None else self._csv_fpaths[0]

        # the GIS file is common to all CSVs - if not provided, defaults to the first CSV
        self._has_gis = gis_fpath is not None
        #: Path: Path to the GIS file common to all CSV files. Defaults to the first CSV file if no GIS file is given.
        self.gis_fpath = TuflowPath(gis_fpath) if gis_fpath else TuflowPath(fpath[0])
        self.dt_decimal_places = dt_decimal_places
        self._gis_provider = None
        self._lp = {}  # {label: {data_type: LP2DProvider}}
        

        for f in self._csv_fpaths:
            if not f.exists():
                raise FileNotFoundError(f'File {f} does not exist.')

        if self._has_gis and not self.gis_fpath.exists():
            raise FileNotFoundError(f'Layer {gis_fpath} does not exist.')

        self._load()

    def add_csv(self, fpath: PathLike | Sequence[PathLike]) -> None:
        """Dynamically add one or more ``2d_lp`` CSV files to the output. The files can be for new
        locations (line labels) and/or new data types. If a file for the same location and data type has
        already been loaded, it is replaced.

        Parameters
        ----------
        fpath : PathLike | Sequence[PathLike]
            The CSV file path(s) to add.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.add_csv('/path/to/model_LP_NAME_V.csv')
        >>> lp.data_types()
        ['bed level', 'water level', 'velocity', 'max water level', 'max velocity']
        """
        if isinstance(fpath, (str, Path)):
            fpath = [fpath]
        fpath = [Path(x) for x in fpath]
        for f in fpath:
            if not f.exists():
                raise FileNotFoundError(f'File {f} does not exist.')
        for f in fpath:
            self._add_provider(f)
        self._rebuild()

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Because all locations
        share the same timestamps, the filter_by argument has no practical effect for this class.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the times by.
        fmt : str, optional
            The format for the times. Options are :code:`relative` or :code:`absolute`.

        Returns
        -------
        list[TimeLike]
            The available times in the requested format.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        """
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The chainages along the 2d_lp line will each be given a unique ID based on the name of the 2d_lp line.
        If a GIS file is provided, the label will be extracted from the "label" field. If no GIS file is provided,
        the line label cannot be determined, so the file name excluding the data type is used.

        Point IDs will be made up as ``[label]_[offset]_pnt[index]``.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters objects for the
        ``LP2D`` class are:

        * ``None``: default - returns all IDs
        * ``2d``: same as ``None`` as class only contains 2D data
        * ``node`` / ``point``: returns only point IDs
        * ``nodestring`` / ``line``: returns only line IDs
        * ``timeseries``: returns only IDs that have time series data (same as ``point`` for the ``LP2D`` class).
        * ``section``: returns only IDs that have section data (i.e. long plot data - same as ``line`` for the ``LP2D`` class).
        * ``[data_type]``: returns only IDs for the given data type. Shorthand data type names can be used.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.ids()
        ['EG02_012_LP_01_2.07_pnt0', 'EG02_012_LP_01_8.31_pnt1', 'EG02_012_LP_01_14.55_pnt2', ..., 'EG02_012_LP_01']
        """
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        2d_lp outputs will typically have bed level and maximum values recorded along with the given result type.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``LP2D`` class are:

        * ``None``: default - returns all available data types
        * ``2d``: same as ``None`` as class only contains 2D data
        * ``node`` / ``point``: returns only node data types. Won't have much affect as line and point data types
          will be the same.
        * ``nodestring`` / ``line``: returns only nodestring data types. Won't have much affect as line and
          point data types will be the same.
        * ``static`` / ``temporal`` returns static or temporal result types.
        * passing an ID string: returns only data types for the given ID.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.data_types()
        ['bed level', 'water level', 'max water level']
        """
        filter_by_ = filter_by.split('/') if filter_by else None

        # temporal filter
        temporal = False
        temporal_types = {'temporal', 'timeseries', 'point', 'node'}
        for temp_type in temporal_types:
            while filter_by_ and temp_type in filter_by_:
                temporal = True
                filter_by_.remove(temp_type)


        # static filter
        static = False
        static_types = {'static'}
        for temp_type in static_types:
            while filter_by_ and temp_type in filter_by_:
                static = True
                filter_by_.remove(temp_type)

        if temporal and static:
            return []  # can't filter by both static and temporal
        elif temporal:
            filter_by = '/'.join(['point'] + filter_by_ if filter_by_ else  [])

        if static:
            data_types_ = super().data_types()
            data_types = []
        else:
            data_types_ = super().data_types(filter_by)
            data_types = data_types_
            if temporal:
                return data_types
        max_types = [f'max {x}' for x in data_types_]
        return ['bed level'] + data_types + max_types

    def maximum(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`h` for :code:`water level`.

        The returned DataFrame will have an index column corresponding to the location IDs, and the columns
        will be in the format :code:`obj/data_type/[max|tmax]`,
        e.g. :code:`point/water level/max`, :code:`point/water level/tmax`

        The ``maximum()`` method is only applicable for points along the 2d_lp line. For the maximum profile
        result, use the :meth:`section()<pytuflow.LP2D.section>` method with the data type of
        ``max [data_type]`` e.g. ``max water level``.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the maximum values for. :code:`None` will return all locations for the
            given data_types.
        data_types : str | list[str]
            The data types to extract the maximum values for. :code:`None` will return all data types for the
            given locations.
        time_fmt : str, optional
            The format for the time of max result. Options are :code:`relative` or :code:`absolute`

        Returns
        -------
        pd.DataFrame
            The maximum, and time of maximum values

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.maximum('EG02_012_LP_01_2.07_pnt0', 'water level')
                                   point/water level/max  point/water level/tmax
        EG02_012_LP_01_2.07_pnt0                  49.863                  0.9500
        """
        return super().maximum(locations, data_types, time_fmt)

    def time_series(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s). The ``time_series()``
        method is only applicable for points along the 2d_lp line.

        The returned column names will be in the format :code:`obj/data_type/location`
        e.g. :code:`point/water level/<label>_<distance>_pnt0`.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the time series data for. If :code:`None` is passed in, all locations will be
            returned for the given data_types.
        data_types : str | list[str]
            The data type to extract the time series data for. If :code:`None` is passed in, all data types
            will be returned for the given locations.
        time_fmt : str, optional
            The format for the time column. Options are :code:`relative` or :code:`absolute`.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> id_ = lp.ids()[0]  # get the first available ID for demonstration
        >>> print(id_)
        EG02_012_LP_01_2.07_pnt0
        >>> df = lp.time_series(id_, 'water level')
                point/water level/EG02_012_LP_01_2.07_pnt0
        time
        0.0000                                      44.135
        0.0167                                      44.135
        0.0333                                      44.135
        0.0500                                      44.135
        0.0667                                      44.135
        ...                                            ...
        2.9333                                      48.583
        2.9500                                      48.570
        2.9667                                      48.556
        2.9833                                      48.543
        3.0000                                      48.530
        """
        return super().time_series(locations, data_types, time_fmt)

    def section(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
        """Returns a DataFrame containing the long plot data for the given location(s) and data type(s).

        The returned DataFrame will have the following columns:

        * :code:`branch_id`: The ID of the branch (nodestring) that the data is from (for ``LP2D.section()`` calls
          this will always be zero).
        * :code:`node_string`: The name of the nodestring.
        * :code:`offset`: The offset along the nodestring.
        * :code:`data_type`: The data type (e.g. water level).

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the long plot data for (i.e. the nodestring names).
        data_types : str | list[str]
            The data types to extract the long plot data for.
        time : TimeLike
            The time to extract the long plot data for.

        Returns
        -------
        pd.DataFrame
            The long plot data.

        Examples
        --------
        >>> lp = LP2D('/path/to/model_LP_NAME_H.csv')
        >>> lp.section('model_LP_NAME', 'h', 1.)
           offset  branch_id     node_string       h
        0    2.07          0  EG02_012_LP_01  49.862
        1    8.31          0  EG02_012_LP_01  49.860
        2   14.55          0  EG02_012_LP_01  49.873
        3   20.79          0  EG02_012_LP_01  49.148
        4   27.03          0  EG02_012_LP_01  46.414
        5   33.28          0  EG02_012_LP_01  47.090
        6   39.52          0  EG02_012_LP_01  47.094
        7   45.77          0  EG02_012_LP_01  47.072
        8   52.02          0  EG02_012_LP_01  47.040
        """
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        locations, data_types = self._figure_out_loc_and_data_types_lp(locations, data_types, 'section')

        data_types_copy = data_types.copy()

        df_all = []
        for i, label in enumerate(self._section_labels(locations)):
            df = self._section_label(label, data_types, time)
            if df is None or df.empty:
                continue
            df.reset_index(inplace=True)
            df['branch_id'] = i
            df['node_string'] = label
            df_all.append(df[['offset', 'branch_id', 'node_string'] + [x for x in data_types_copy if x in df.columns]])

        if not df_all:
            return pd.DataFrame()
        return pd.concat(df_all, axis=0, ignore_index=True)

    def _section_labels(self, locations: list[str]) -> list[str]:
        labels = {x.lower(): x for x in self._lp}
        return [labels[x.lower()] for x in locations if x.lower() in labels]

    def _section_label(self, label: str, data_types: list[str], time: TimeLike) -> pd.DataFrame | None:
        providers = self._lp[label]
        df = None
        for dtype in data_types:
            if dtype == 'bed level':
                a = list(providers.values())[0].bed_level()
            elif dtype.startswith('max '):
                provider = providers.get(self._get_standard_data_type_name(dtype[4:]))
                if not provider:
                    continue
                a = provider.maximum_section()
            else:
                provider = providers.get(self._get_standard_data_type_name(dtype))
                if not provider:
                    continue
                a = provider.get_section('', time, False)
            df1 = pd.DataFrame(a[:, 1], index=a[:, 0], columns=[dtype])
            df1.index.name = 'offset'
            if not df1.empty:
                df = pd.concat([df, df1], axis=1) if df is not None else df1
        return df

    def curtain(self, *args, **kwargs) -> pd.DataFrame:
        """no-doc"""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, *args, **kwargs) -> pd.DataFrame:
        """no-doc"""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _load(self):
        if self.objs is not None and not self.objs.empty:
            return
        if self._has_gis:
            self._gis_provider = LongProfileGIS(self.gis_fpath, id_col_name='Label')
        for fpath in self._csv_fpaths:
            self._add_provider(fpath)
        if self._has_gis:
            self.name = self.gis_fpath.stem
        else:
            self.name = next(iter(self._lp))
        self._rebuild()

    def _add_provider(self, fpath: Path) -> None:
        lp = LP2DProvider(fpath, self.gis_fpath if self._has_gis else None, self._gis_provider)
        data_type = self._data_type(lp.fpath.stem)
        label = lp.get_labels()[0]
        self._lp.setdefault(label, {})[data_type] = lp
        fpath = lp.fpath
        if fpath not in self._csv_fpaths:
            self._csv_fpaths.append(fpath)

    def _rebuild(self) -> None:
        self._time_series_data.clear()
        self._maximum_data.clear()
        self._load_time_series()
        self._load_maximums()
        self._load_obj_df()
        self.node_string_count = len(self._lp)
        self.node_count = int(self.objs['geometry'].value_counts().get('point', 0))

    def _data_type(self, filename: str):
        part = filename.split('_')[-1]
        return self._get_standard_data_type_name(part)

    def _providers(self):
        for label, providers in self._lp.items():
            for data_type, provider in providers.items():
                yield label, data_type, provider

    def _load_time_series(self):
        for _, data_type, provider in self._providers():
            df = pd.DataFrame(
               provider.get_time_series_data_raw(''),
               index=provider.get_timesteps(),
               columns=provider.pnt_labels,
            )
            df.index.name = 'time'
            self._time_series_data[data_type] = df

    def _load_maximums(self) -> None:
        """Load the result maximums."""
        for _, data_type, provider in self._providers():
            df = pd.DataFrame(
                provider.maximum(),
                index=provider.pnt_labels,
                columns=['max', 'tmax']
            )
            self._maximum_data[data_type] = df

    def _load_obj_df(self):
        info = {'id': [], 'data_type': [], 'geometry': [], 'domain': [], 'start': [], 'end': [], 'dt': []}
        for label, dtype, provider in self._providers():
            times = provider.get_timesteps()
            if len(times) == 0:
                continue
            dt = np.round((times[1] - times[0]) * 3600., decimals=self.dt_decimal_places) if len(times) > 1 else np.nan
            for id_, geom in [(x, 'point') for x in provider.pnt_labels] + [(label, 'line')]:
                info['id'].append(id_)
                info['data_type'].append(dtype)
                info['geometry'].append(geom)
                info['domain'].append('2d')
                info['start'].append(times[0])
                info['end'].append(times[-1])
                info['dt'].append(dt)

        self.objs = pd.DataFrame(info)
