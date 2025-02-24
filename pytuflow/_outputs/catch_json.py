import json
from pathlib import Path
from collections import OrderedDict
from typing import Union

import numpy as np
import pandas as pd

from .map_output import MapOutput, PointLocation, LineStringLocation
from .mesh import Mesh
from .._pytuflow_types import PathLike, TimeLike
from .helpers.catch_providers import CATCHProvider
from ..util._util.misc_tools import flatten


class CATCHJson(MapOutput):

    def __init__(self, fpath: PathLike | str):
        super().__init__(fpath)
        self._fpath = Path(fpath)
        self._data = {}
        self._providers = OrderedDict()
        self._idx_provider = None
        self._load_json(fpath)
        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return True

    @staticmethod
    def _looks_empty(fpath: Path) -> bool:
        return False

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        return super().times(filter_by, fmt)

    def data_types(self, filter_by: str = None) -> list[str]:
        return super().data_types(filter_by)

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', averaging_method: str = None) -> pd.DataFrame:
        df = pd.DataFrame()
        for provider in self._providers.values():
            df = provider.time_series(locations, data_types, time_fmt, averaging_method)
            if not df.empty:
                break
        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, averaging_method: str = None) -> pd.DataFrame:
        df = pd.DataFrame()
        locations = self._translate_line_string_location(locations)

        # don't want to deal with multiple locations when stitching results together
        for loc, line in locations.items():
            loc = {loc: line}
            dfs = []
            df1 = pd.DataFrame()
            for provider in self._providers.values():
                df2 = provider.section(loc, data_types, time, averaging_method)
                if not df2.empty:
                    dfs.append((df2, provider._driver.start_end_locs.copy()))

            if dfs:
                for df2, start_end_locs in reversed(dfs):
                    for start_loc, end_loc in start_end_locs:
                        if df1.empty:
                            df1 = df2
                        else:
                            df1 = self._insert_df_info_df_by_distances(df1, df2, start_loc, end_loc, None)

            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        df = pd.DataFrame()
        locations = self._translate_line_string_location(locations)

        # don't want to deal with multiple locations when stitching results together
        for locname, line in locations.items():
            loc = {locname: line}
            dfs = []
            df1 = pd.DataFrame()
            for provider in self._providers.values():
                df2 = provider.curtain(loc, data_types, time)
                if not df2.empty:
                    dfs.append((df2, provider._driver.start_end_locs.copy()))

            if dfs:
                for df2, start_end_locs in reversed(dfs):
                    for start_loc, end_loc in start_end_locs:
                        if df1.empty:
                            df1 = df2
                            break
                        else:
                            df1 = self._stamp(df1, df2, start_loc, end_loc)

            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, interpolation: str = 'stepped') -> pd.DataFrame:
        pass

    def _load_json(self, fpath: PathLike | str):
        if Path(fpath).is_file():
            with Path(fpath).open() as f:
                self._data = json.load(f, object_pairs_hook=OrderedDict)
        else:
            self._data = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(fpath)

    def _initial_load(self):
        self.name = self._data.get('name')
        default_time_string = 'hours since 1990-01-01 00:00:00'
        self.reference_time, _ = self._parse_time_units_string(self._data.get('time units', default_time_string),
                                                        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                                                        '%Y-%m-%d %H:%M:%S')
        self.units = self._data.get('units', 'metric')
        self._outputs = self._data.get('output data', {})
        self._result_types = [Mesh._get_standard_data_type_name(x) for x in self._data.get('result types')]

        index_result_name = self._data.get('index')
        for res_name, output in self._outputs.items():
            provider = CATCHProvider.from_catch_json_output(self._fpath.parent, output)
            if res_name == index_result_name:
                self._idx_provider = provider
            self._providers[res_name] = provider

        self._load_info()

    def _load_info(self):
        self._info = pd.DataFrame(columns=['data_type', 'type', 'is_max', 'is_min', 'static', 'start', 'end', 'dt'])
        for provider in self._providers.values():
            if provider == self._idx_provider:
                continue
            if provider.reference_time != self.reference_time:
                provider.offset_time = (provider.reference_time - self.reference_time).total_seconds()
            df = provider.info_with_correct_times()
            self._info = pd.concat([self._info, df], axis=0) if not self._info.empty else df

        self._info = self._info.drop_duplicates()

    def _stamp(self, df1: pd.DataFrame, df2: pd.DataFrame, start_loc: float, end_loc: float):
        mask = df1.iloc[:,0] <= start_loc
        inds = np.where(~mask)
        mask2 = (df2.iloc[:,0] >= start_loc) & (df2.iloc[:,0] <= end_loc)
        df2_ = df2[mask2]
        if not inds or not inds[0].size:
            if df1.iloc[0,0] < start_loc:
                return pd.concat([df1, df2_], axis=0, ignore_index=True)
            else:
                return pd.concat([df2_, df1], axis=0, ignore_index=True)

        df = df1.iloc[:inds[0][0],:]
        if not df.empty:
            i = inds[0][0]
            val = df1.iloc[i-2,0] if i > 1 else df1.iloc[0,0]
            if not np.isclose(val, start_loc):
                a = [[start_loc] + df1.iloc[i, 1:].tolist(),
                     [start_loc] + df1.iloc[i+1, 1:].tolist(),
                     df1.iloc[i+2,:].tolist()]
                df = pd.concat([df, pd.DataFrame(a)], axis=0, ignore_index=True)

        df = pd.concat([df, df2_], axis=0, ignore_index=True) if not df.empty else df2_

        mask = df1.iloc[:,0] >= end_loc
        inds = np.where(mask)
        if not inds or not inds[0].size:
            return df

        i = inds[0][0]
        val = df1.iloc[i,0]
        if not np.isclose(val, end_loc):
            a = [[end_loc] + df1.iloc[i, 2:].tolist(),
                 df1.iloc[i+1,:].tolist(),
                 df1.iloc[i+2:].tolist(),
                 [end_loc] + df1.iloc[i+3, 2:].tolist()]
            i += 4
            df = pd.concat([df, pd.DataFrame(a)], axis=0, ignore_index=True)

        df = pd.concat([df, df1.iloc[i:,:]], axis=0, ignore_index=True)

        return df

    def _insert_df_info_df_by_distances(self, df1: pd.DataFrame, df2: pd.DataFrame, start_loc: float, end_loc: float,
                                        context: str) -> pd.DataFrame:
        """Combines two section dataframes based on the start/end locations.
        Start / end locations are distances along the line where df2 should be stamped onto df1.
        """
        # mask data by start / end distances
        i = -1
        if not df1.empty:  # consider case where df1 is empty
            # what is being kept from df1
            mask1 = (df1.iloc[:,0] < start_loc) | (df1.iloc[:,0] > end_loc)
            if context == 'polygon':  # curtain plot data
                mask1 = (start_loc <= df1.iloc[:,0]) & (df1.iloc[:,2] <= end_loc) == False
                i = self._find_overlaps(df1, start_loc, end_loc)
            # elif context == 'vector':
            #     mask1 = (start_loc <= df1[5]) & (df1[6] <= end_loc) == False
            #     i = self._find_overlaps_vectors(df1, start_loc, end_loc)

        # what is being used from df2
        mask2 = (df2.iloc[:,0] >= start_loc) & (df2.iloc[:,0] <= end_loc)

        # for cell face data (not vertex data), there will be duplicate distances (data will step from cell to cell)
        if (df2.iloc[:,0] == start_loc).sum() == 2:
            j = df2.iloc[:,0].tolist().index(start_loc)
            if j != 0:
                mask2[j] = False
        if (df2.iloc[:,0] == end_loc).sum() == 2:
            j = df2.iloc[:,0].tolist().index(end_loc) + 1
            if j + 1 != df2.shape[0]:
                mask2[j] = False

        # apply masks
        df1_ = df1
        if not df1.empty:
            df1_ = df1[mask1]
            if i == -1:
                if False in mask1.tolist():
                    i = mask1.tolist().index(False)  # where new data needs to be inserted
                else:
                    i = 0 if df1.iloc[:,0].min() > end_loc else -1
        df2_ = df2[mask2]

        # concatenate data together
        if i == -1:
            data = pd.concat([df1_, df2_], ignore_index=True)
        else:
            data = pd.concat([df1_.iloc[:i], df2_, df1_.iloc[i:]], ignore_index=True)

        return data

    @staticmethod
    def _find_overlaps(df: pd.DataFrame, start_dist: float, end_dist: float):
        """For curtain plot data, shorten overlapping boxes to start / end distances."""
        if not df.empty:  # consider case where df1 is empty
            overlap_mask_1 = (df.iloc[:,2] > start_dist) & (df.iloc[:,0] < start_dist)
            for i, ind in enumerate(df.index[overlap_mask_1].tolist()):
                df.iloc[i, 2] = start_dist
            overlap_mask_2 = (df.iloc[:,0] < end_dist) & (df.iloc[:,2] > end_dist)
            for j, ind in enumerate(df.index[overlap_mask_2].tolist()):
                df.iloc[j, 0] = end_dist
            if df.index[overlap_mask_1].tolist():
                return df.index[overlap_mask_1].tolist()[-1] + 1
            return -1

        return -1

    @staticmethod
    def _find_overlaps_vectors(df: pd.DataFrame, start_dist: float, end_dist: float):
        if not df.empty:
            overlap_mask_1 = (df[6] > start_dist) & (df[5] < start_dist)
            for i in df.index[overlap_mask_1].tolist():
                df.loc[i, 1] = (df.loc[i, 5] + start_dist) / 2.
            overlap_mask_2 = (df[5] < end_dist) & (df[6] > end_dist)
            for j in df.index[overlap_mask_2].tolist():
                df.loc[j, 1] = (df.loc[j, 6] + end_dist) / 2.
                if df.index[overlap_mask_1].tolist():
                    return df.index[overlap_mask_1].tolist()[-1] + 1
                return -1
        return -1
