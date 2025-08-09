import json
import re
import typing
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from pytuflow._pytuflow_types import PathLike, TimeLike, PlotExtractionLocation


with (Path(__file__).parent / 'data' / 'data_type_name_alternatives.json').open() as f:
    DATA_TYPE_NAME_ALTERNATIVES = json.load(f)

DEFAULT_REFERENCE_TIME = datetime(1990, 1, 1)


class Output(ABC):
    """Base class for all TUFLOW output classes. This class should not be initialised directly."""

    DOMAIN_TYPES = {}
    GEOMETRY_TYPES = {}
    ATTRIBUTE_TYPES = {}
    ID_COLUMNS = []

    @abstractmethod
    def __init__(self, *fpath: PathLike, **kwargs) -> None:
        super().__init__()
        self._fpath = fpath

        #: str: The result name
        self.name = ''
        #: datetime: The reference time for the output
        self.reference_time = datetime(2000, 1, 1, tzinfo=timezone.utc)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.name})"

    @staticmethod
    def _looks_like_this(*fpath: PathLike) -> bool:
        """Check if the given file(s) look like this output type.

        Parameters
        ----------
        fpath : PathLike
            The path to the output file(s).

        Returns
        -------
        bool
            True if the file(s) look like this output type.
        """
        return True

    @staticmethod
    def _looks_empty(*fpath: PathLike) -> bool:
        """Check if the given file(s) look empty or incomplete.

        Parameters
        ----------
        fpath : PathLike
            The path to the output file(s).

        Returns
        -------
        bool
            True if the file(s) look empty.
        """
        return False

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given context.

       The context is an optional input that can be used to filter the return further. E.g. this can be used to
       get the times only for a given 1D channel.

       Parameters
       ----------
       filter_by : str, optional
           The context to filter the times by.
       fmt : str, optional
           The format for the times. Options are 'relative' or 'absolute'.

       Returns
       -------
       list[TimeLike]
           The available times in the requested format.
       """
        def generate_times(row):
            if isinstance(row['dt'], tuple):
                return np.array(row['dt'])
            else:
                if np.isclose(row['start'], row['end'], rtol=0., atol=0.001).all():
                    return np.array([])
                a = np.arange(row['start'], row['end'], row['dt'] / 3600.)
                if not np.isclose(a[-1], row['end'], rtol=0., atol=0.001):
                    a = np.append(a, np.reshape(row['end'], (1,)), axis=0)
                return a[a <= row['end']]

        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self._filter(filter_by)
        if ctx.empty:
            return []
        if not np.intersect1d(['start', 'end', 'dt'], ctx.columns).all():
            return []

        # generate a lit of times based on the unique start, end and dt values
        time_prop = ctx[['start', 'end', 'dt']].drop_duplicates()
        time_prop['times'] = time_prop.apply(generate_times, axis=1)
        combined_times = pd.Series([time for times_list in time_prop['times'] for time in times_list])
        unique_sorted_times = pd.Series(combined_times.unique()).sort_values().reset_index(drop=True)

        if fmt == 'absolute':
            return [self.reference_time + timedelta(hours=x) for x in unique_sorted_times.tolist()]
        return unique_sorted_times.tolist()

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the context.

        The ``filter_by`` is an optional input that can be used to filter the return further. E.g. this can be used to
        return only data types that contain maximum results.

        Parameters
        ----------
        filter_by : str, optional
            The context to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.
        """
        ctx = self._filter(filter_by)
        if ctx.empty:
            return []

        return ctx['data_type'].unique().tolist()

    @abstractmethod
    def time_series(self, locations: PlotExtractionLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', **kwargs) -> pd.DataFrame:
        """Returns a time series dataframe for the given location and data type. The return DataFrame may have multiple
        time columns if the output time series data do not share a common time key.

        Parameters
        ----------
        locations : PlotExtractionLocation
            The location to extract the time series data for.
        data_types : str | list[str]
            The data type to extract the time series data for.
        time_fmt : str, optional
            The format for the time column. Options are 'relative' or 'absolute'.

        Returns
        -------
        pd.DataFrame
            The time series data.
        """
        pass

    @abstractmethod
    def section(self, locations: PlotExtractionLocation, data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Returns a section dataframe for the given location and data type.

        Parameters
        ----------
        locations : PlotExtractionLocation
            The location to extract the section data for.
        data_types : str | list[str]
            The data type to extract the section data for.
        time : TimeLike
            The time to extract the section data for.

        Returns
        -------
        pd.DataFrame
            The section data.
        """
        pass

    @abstractmethod
    def curtain(self, locations: PlotExtractionLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a dataframe containing curtain plot data for the given location and data type.

        Parameters
        ----------
        locations : PlotExtractionLocation
            The location to extract the curtain data for.
        data_types : str | list[str]
            The data type to extract the curtain data for.
        time : TimeLike
            The time to extract the curtain data for.

        Returns
        -------
        pd.DataFrame
            The curtain data.
        """
        pass

    @abstractmethod
    def profile(self, locations: PlotExtractionLocation, data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Returns a dataframe containing vertical profile data for the given location and data type.

        Parameters
        ----------
        locations : PlotExtractionLocation
            The location to extract the profile data for.
        data_types : str | list[str]
            The data type to extract the profile data for.
        time : TimeLike
            The time to extract the profile data for.

        Returns
        -------
        pd.DataFrame
            The profile data.
        """
        pass

    def _overview_dataframe(self) -> pd.DataFrame:
        pass

    def _filter(self, filter_by: str, filtered_something: bool = False, df: pd.DataFrame = None,
                ignore_excess_filters: bool = False) -> pd.DataFrame:
        """Returns a DataFrame with the output combinations for the given filter string.

        Parameters
        ----------
        filter_by : str
            The context to extract the combinations for.
        filtered_something : bool, optional
            Sets the filtered_something flag to True immediately. This allows the method to be overridden in subclasses,
            and to call the super() method with some filtering already applied.
        df : pd.DataFrame, optional
            Sets the DataFrame to filter. If not provided, it will use the overview DataFrame. This allows the method to
            be overridden in subclasses and to call the super() method with some filtering already applied.
        ignore_excess_filters : bool, optional
            If True, the method will ignore any filters that do not match any of the available contexts. Otherwise,
            leftover filters will result in an empty DataFrame.

        Returns
        -------
        pd.DataFrame
            The context combinations.
        """
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        df = self._overview_dataframe() if df is None else df
        if not filter_by:
            return df

        # domain
        if self.DOMAIN_TYPES:
            df, filtered_something_ = self._filter_generic(filter_by, df, self.DOMAIN_TYPES, 'domain')
            if filtered_something_:
                filtered_something = True

        # geometry
        if self.GEOMETRY_TYPES:
            df, filtered_something_ = self._filter_generic(filter_by, df, self.GEOMETRY_TYPES, 'geometry')
            if filtered_something_:
                filtered_something = True

        # attribute types
        if self.ATTRIBUTE_TYPES:
            df, filtered_something_ = self._filter_generic(filter_by, df, self.ATTRIBUTE_TYPES, 'type')
            if filtered_something_:
                filtered_something = True
            elif any([x for x in filter_by if x.lower() in [x.lower() for x in self.ATTRIBUTE_TYPES]]):
                df = pd.DataFrame(columns=df.columns)

        # data types
        df, filtered_something_ = self._filter_by_data_type(filter_by, df)
        if filtered_something_:
            filtered_something = True

        # ids
        df, filtered_something_ = self._filter_by_id(self.ID_COLUMNS, filter_by, df)
        if filtered_something_:
            filtered_something = True

        return df if not df.empty and filtered_something and not (filter_by and not ignore_excess_filters) else pd.DataFrame(columns=df.columns)

    @staticmethod
    def _get_standard_data_type_name(name: str) -> str:
        """no-doc

        Returns the standard data type name for a given name. The name can be a short name, long name, or
        any standard alternate name of the given data type.
        """
        for key, vals in DATA_TYPE_NAME_ALTERNATIVES['data_types'].items():
            if name.lower() == key.lower():
                return key
            for val in vals:
                if re.match(fr'^(?:(?:t?max(?:imum)?|time[\s_-]+of[\s_-]+peak)(?:\s|_|-)?)?{val}(?:(?:\s|_|-)?t?max(?:imum)?)?$', name,
                            re.IGNORECASE):
                    if '\\d' in key:
                        n = re.findall(r'\d+', name)
                        return key.replace('\\d', n[0]) if n else key
                    return key

        return name.lower()

    def _load(self):
        pass

    @staticmethod
    def _parse_time_units_string(string: str, regex: str, fmt: str) -> tuple[datetime, str]:
        """Parses a string containing the time units and reference time
        e.g. hours since 1990-01-01 00:00:00
        Returns the reference time as a datetime object, the time units as a single character.

        Parameters
        ----------
        string : str
           String containing the time units and reference time.
        regex : str
            Regular expression to match the format of the reference time.
        fmt : str
            Format of the reference time.

        Returns
        -------
        tuple[datetime, str]
            Reference time and time units.
        """
        if 'hour' in string:
            u = 'h'
        elif 'minute' in string:
            u = 'm'
        elif 'second' in string:
            u = 's'
        elif 'since' in string:
            u = string.split(' ')[0]
        else:
            u = string
        time = re.findall(regex, string)
        if time:
            return datetime.strptime(time[0], fmt), u
        return DEFAULT_REFERENCE_TIME, u

    @staticmethod
    def _closest_time_index(
            timesteps: list[TimeLike],
            time: TimeLike,
            method: str = 'previous',
            tol: float = 0.001
    ) -> int:
        """Returns the index of the closest time in the provided timesteps.
        It will try and find any matching time within the given tolerance, otherwise will return the index of the
        previous or next time depending on the method.
        """
        if isinstance(time, datetime):
            a = np.array([abs((x - time).total_seconds()) for x in timesteps])
        else:
            a = np.array([abs(x - time) for x in timesteps])

        isclose = np.isclose(a, 0, rtol=0., atol=tol)
        if isclose.any():
            return int(np.argwhere(isclose).flatten()[0])

        if method == 'previous':
            prev = a < time
            if prev.any():
                return int(np.argwhere(prev).flatten()[-1])
            else:
                return 0
        elif method == 'next':
            next_ = a > time
            if next_.any():
                return int(np.argwhere(next_).flatten()[0])
            else:
                return len(timesteps) - 1

        return 0

    @staticmethod
    def _filter_generic(ctx: list[str],
                   df: pd.DataFrame,
                   possible_types: dict[typing.Any, list[str]],
                   column_name: str,
                   exclude: bool = False) -> tuple[pd.DataFrame, bool]:
        def remove_from_ctx(ctx1, types):
            for typ in types:
                while typ in ctx1:
                    ctx1.remove(typ)

        filtered_something = False
        ctx_ = []
        for typ, aliases in possible_types.items():
            if np.intersect1d(ctx, aliases).size:
                filtered_something = True
                ctx_.append(typ)
                remove_from_ctx(ctx, aliases)

        if filtered_something:
            if ctx_ and isinstance(ctx_[0], str):
                df = df[df[column_name].str.lower().isin(ctx_)] if not exclude else df[~df[column_name].str.lower().isin(ctx_)]
            else:
                df = df[df[column_name].isin(ctx_)] if not exclude else df[~df[column_name].isin(ctx_)]

        return df, filtered_something

    def _filter_by_data_type(self, ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        filtered_something = False
        if 'data_type' not in df.columns:
            return df, filtered_something
        for i in range(len(ctx)):
            max_ = 'max' in ctx[i].lower()
            ctx[i] = self._get_standard_data_type_name(ctx[i])
            if max_:
                ctx[i] = f'max {ctx[i]}'
        ctx_dict = {x: [x] for x in ctx if x in df['data_type'].unique()}
        if ctx_dict:
            df, filtered_something = self._filter_generic(ctx, df, ctx_dict, 'data_type')
        return df, filtered_something

    @staticmethod
    def _filter_by_id(id_cols: list[str], ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        filtered_something = False
        if not ctx or df.empty:
            return df, filtered_something

        df1 = pd.DataFrame()
        for id_ in id_cols:
            df2 = df[df[id_].str.lower().isin(ctx)]
            if not df2.empty:
                filtered_something = True
                df1 = pd.concat([df1, df2], axis=0) if not df1.empty else df2
            if not df.empty:
                j = len(ctx) - 1
                for i, x in enumerate(reversed(ctx.copy())):
                    if df[id_].str.lower().isin([x.lower()]).any():
                        ctx.pop(j - i)

        df = df1 if not df1.empty else df
        return df, filtered_something
