from collections.abc import Sequence
import numpy as np

try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

from .time_series import TimeSeries
from ..misc import AppendDict
from .._pytuflow_types import TimeLike


class LongProfileBase(TimeSeries):
    GEOMETRY_TYPES = {'2d': ['2d'], 'point': ['node', 'timeseries', 'point'],
                      'line': ['section', 'nodestring', 'line']}
    ATTRIBUTE_TYPES = {}
    ID_COLUMNS = ['id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        #: LongProfileBaseProvider: The provider for the long profile output
        self.provider = None
        #: pd.DataFrame: Result objects
        self.objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])
        #: int: Number of nodes
        self.node_count = 0
        #: int: Number of node strings
        self.node_string_count = 0
        # private
        self._time_series_data = AppendDict()
        self._maximum_data = AppendDict()

    def maximum(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time_fmt: str = 'relative') -> pd.DataFrame:
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        locations, data_types = self._figure_out_loc_and_data_types(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx, _ = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        df = self._maximum_extractor(ctx[ctx['geometry'] == 'point'].data_type.unique(), data_types,
                                     self._maximum_data, ctx, time_fmt, self.reference_time)
        df.columns = [f'point/{x}' for x in df.columns]

        return df

    def time_series(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:

        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2
        df = self._time_series_extractor(ctx[ctx['geometry'] == 'point'].data_type.unique(), data_types,
                                         self._time_series_data, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = [f'point/{x}' for x in df.columns]

        return df

    def section(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        locations, data_types = self._figure_out_loc_and_data_types_lp(locations, data_types, 'section')

        df = pd.DataFrame()
        for i, loc in enumerate(locations):
            for dtype in data_types:  # assume only water level is possible
                a = self.provider.get_section(loc, time, False)
                df1 = pd.DataFrame(a, columns=['offset', dtype])
                df1['branch_id'] = i
                df1['node_string'] = loc
                df1 = df1[['branch_id', 'node_string', 'offset', dtype]]
                df = df1 if df.empty else pd.concat([df, df1], axis=0)

        return df

    def curtain(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``FVBCTide`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: str | Sequence[str] | None, data_types: str | Sequence[str] | None,
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``FVBCTide`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _overview_dataframe(self) -> pd.DataFrame:
        return self.objs.copy()

    def _load_time_series(self):
        df = pd.DataFrame()
        for label in self.provider.get_labels():
            df1 = pd.DataFrame(
                self.provider.get_time_series_data_raw(label),
                index=self.provider.get_timesteps('relative'),
                columns=[f'{label}_pt_{x}' for x in range(self.provider.number_of_points(label))]
            )
            df = df1 if df.empty else pd.concat([df, df1], axis=1)

        if not df.empty:
            df.index.name = 'time'

        self._time_series_data['water level'] = df

    def _load_maximums(self) -> None:
        """Load the result maximums."""
        # info class does not have actual maximums, so need to be post-processed.
        for data_type, results in self._time_series_data.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                self._maximum_data[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

    def _load_obj_df(self):
        info = {'id': [], 'data_type': [], 'geometry': [], 'domain': [], 'start': [], 'end': [], 'dt': []}
        dt, start, end = np.nan, np.nan, np.nan
        for dtype, vals in self._time_series_data.items():
            for df1 in vals:
                if df1.empty:
                    continue
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    info['id'].append(col)
                    info['data_type'].append(dtype)
                    info['geometry'].append('point')
                    info['domain'].append('fvbctide')
                    info['start'].append(start)
                    info['end'].append(end)
                    info['dt'].append(dt)

        for label in self.provider.get_labels():
            info['id'].append(label)
            info['data_type'].append('water level')
            info['geometry'].append('line')
            info['domain'].append('fvbctide')
            info['start'].append(start)
            info['end'].append(end)
            info['dt'].append(dt)

        self.objs = pd.DataFrame(info)
