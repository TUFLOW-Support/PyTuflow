import io
import os
import typing
from collections import OrderedDict
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .converter import Converter
from ..output import Output, OutputCollection
from ..helpers.geometry import generate_bridge_section, parabolic_arch_conduit, create_hw_table, Line
from ..helpers.tuflow_empty_files import tuflow_empty_field_map
from ..helpers.settings import get_fm2estry_settings, Settings

if typing.TYPE_CHECKING:
    from ..parsers.units.bridge import Bridge as BridgeHandler


class ArchBridge(Converter):

    def __init__(self, unit: 'BridgeHandler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.nwk = Output('GIS', unit.uid)
            self.xs = Output('FILE', unit.uid)
            self.hw = Output('FILE', unit.uid)
            self.barch = Output('FILE', unit.uid)
            self.tab = Output('GIS', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'BRIDGE_ARCH'

    def convert(self) -> OutputCollection:
        if self.settings.arch_bridge_approach.upper() == 'BARCH':
            return BArch(self).convert()
        elif self.settings.arch_bridge_approach.upper() == 'I-CULV':
            if self.settings.arch_bridge_culv_approach.upper() == 'SINGLE':
                return ICulv(self).convert()
            elif self.settings.arch_bridge_culv_approach.upper() == 'MULTI':
                return ICulvMulti(self).convert()
        return OutputCollection()

    @staticmethod
    def gen_hw_table(unit: 'BridgeHandler', settings: Settings = None) -> typing.Union[pd.DataFrame, list[pd.DataFrame]]:
        settings = get_fm2estry_settings() if settings is None else settings
        tables = []
        section = unit.xs[['x', 'y']]
        section.set_index('x', inplace=True)
        for _, arch in unit.arches.iterrows():
            section_ = section.copy()
            # make sure the start and finish points are in the section
            if arch.start not in section_.index:
                section_.loc[arch.start] = 0.  # setting to zero first stops future warning
                section_.loc[arch.start] = np.nan
            if arch.finish not in section_.index:
                section_.loc[arch.finish] = 0.  # setting to zero first stops future warning
                section_.loc[arch.finish] = np.nan
            section_.sort_index(inplace=True)
            section_.interpolate(method='index', inplace=True, limit_direction='both')

            # section just where arch is
            section_['deck'] = arch['springing level']  # temporarily assume deck level is equal to springing level
            idx_start = section_.index.get_loc(arch.start)
            if isinstance(idx_start, slice):
                idx_start = section_.reset_index().iloc[idx_start].y.idxmax()
            idx_finish = section_.index.get_loc(arch.finish)
            if isinstance(idx_finish, slice):
                idx_finish = section_.reset_index().iloc[idx_finish].y.idxmax()
            section_ = generate_bridge_section(
                section_.reset_index(drop=False), int(idx_start), int(idx_finish), pd.DataFrame(), as_df=True
            )
            section_ = section_.rename(columns={'y': 'z'})

            # arch
            arch_xs = parabolic_arch_conduit(arch.finish - arch.start, arch.soffit, arch['springing level'], as_df=True)
            arch_xs.x = arch_xs.x + arch.start  # shift the arch to the correct position

            # combine
            section_ = pd.concat([section_, arch_xs[::-1]], axis=0)

            # hw table
            tables.append(create_hw_table(section_, as_df=True))

        if settings.arch_bridge_culv_approach.upper() == 'SINGLE':
            if len(tables) == 1:
                return tables[0]
            tables = [df.set_index('h') for df in tables]
            comb = pd.concat(tables, axis=1)
            comb.sort_index(inplace=True)
            comb.interpolate(method='index', inplace=True, limit_direction='both')
            comb['total_w'] = comb.sum(axis=1)
            return comb[['total_w']].rename(columns={'total_w': 'w'}).reset_index(drop=False)
        else:
            return tables


class BArch:

    def __init__(self, parent: ArchBridge) -> None:
        self.parent = parent

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.append(self.get_barch())
        out_col.append(self.get_nwk())
        out_col.append(self.get_xs())
        out_col.append(self.get_tab())
        out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'BridgeHandler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = unit.uid
        d['Type'] = 'BARCH'
        d['US_Invert'] = -99999.
        d['DS_Invert'] = -99999.
        d['Inlet_Type'] = Path(os.path.relpath(self.parent.barch.fpath, self.parent.nwk.fpath.parent)).as_posix()
        if not np.isnan(unit.skewb):
            d['Width_or_Dia'] = unit.skewb
        d['Height_or_WF'] = unit.cali
        if unit.oflag.upper() == 'ORIFICE' and not np.isnan(unit.cdorifice):
            d['HConF_or_WC'] = unit.cdorifice * -1
        if not np.isnan(unit.rlower):
            d['EntryC_or_WSa'] = unit.rlower
        if not np.isnan(unit.rupper):
            d['ExitC_or_WSb'] = unit.rupper
        return d

    def map_tab_attributes(self, field_map: dict, unit: 'BridgeHandler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Source'] = Path(os.path.relpath(self.parent.xs.fpath, self.parent.tab.fpath.parent)).as_posix()
        d['Type'] = 'XZ'
        d['Column_1'] = 'x'
        d['Column_2'] = 'y'
        return d

    def get_nwk(self) -> Output:
        self.parent.nwk.fpath, self.parent.nwk.lyrname = self.parent.output_gis_file('1d_nwk', 'BRIDGE')
        self.parent.nwk.field_map = tuflow_empty_field_map('1d_nwk')
        self.parent.nwk.geom_type = 2  # ogr.wkbLineString
        self.parent.nwk.content.geom = self.parent.channel_geom(self.parent.unit)
        self.parent.nwk.content.attributes = self.map_nwk_attributes(self.parent.nwk.field_map, self.parent.unit)
        return self.parent.nwk

    def get_barch(self) -> Output:
        self.parent.barch.fpath = self.parent.settings.output_dir / 'csv' / f'{self.parent.unit.uid}_properties.csv'
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.parent.dat.name}/{self.parent.unit.uid}\n')
        self.parent.unit.arches.to_csv(buf, index=False, lineterminator='\n', float_format='%.3f')
        self.parent.barch.content = buf.getvalue()
        return self.parent.barch

    def get_xs(self) -> typing.Union[OutputCollection, Output]:
        self.parent.xs.fpath = self.parent.settings.output_dir / 'csv' / f'{self.parent.unit.uid}.csv'
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.parent.dat.name}/{self.parent.unit.uid}\n')
        self.parent.unit.xs[['x', 'y']].to_csv(buf, index=False, lineterminator='\n')
        self.parent.xs.content = buf.getvalue()
        return self.parent.xs

    def get_tab(self) -> Output:
        self.parent.tab.fpath, self.parent.tab.lyrname = self.parent.output_gis_file('1d_xs', 'BRIDGE')
        self.parent.tab.field_map = tuflow_empty_field_map('1d_tab')
        self.parent.tab.geom_type = 2  # ogr.wkbLineString (gdal may not be installed)
        self.parent.tab.content.geom = self.parent.mid_cross_section_geometry(self.parent.unit)
        self.parent.tab.content.attributes = self.map_tab_attributes(self.parent.tab.field_map, self.parent.unit)
        return self.parent.tab

    def get_ecf(self) -> Output:
        self.parent.ecf.fpath = self.parent.settings.output_dir / f'{self.parent.settings.outname}.ecf'
        self.parent.ecf.content = 'Read GIS Network == {0}'.format(
            self.parent.output_gis_ref(
                Path(os.path.relpath(self.parent.nwk.fpath, self.parent.ecf.fpath.parent)).as_posix(), self.parent.nwk.lyrname
            )
        )
        self.parent.ecf.content = '{0}\nRead GIS Table Links == {1}'.format(
            self.parent.ecf.content,
            self.parent.output_gis_ref(
                Path(os.path.relpath(self.parent.tab.fpath, self.parent.ecf.fpath.parent)).as_posix(), self.parent.tab.lyrname
            )
        )
        return self.parent.ecf


class ICulv:

    def __init__(self, parent: ArchBridge) -> None:
        self.parent = parent
        self.hw_table = None

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.extend(self.get_hw())
        nwks = self.get_nwk()
        if nwks:
            nwk = nwks[0]
        out_col.extend(nwks)
        tabs = self.get_tab()
        if tabs:
            tab = tabs[0]
        out_col.extend(tabs)
        if nwks and tabs:
            out_col.append(self.get_ecf(nwk, tab))
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'BridgeHandler', id_: str, invert: float) -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = id_
        d['Type'] = 'I'
        d['Len_or_ANA'] = 0.01
        d['n_nf_Cd'] = 0.015
        d['US_Invert'] = invert
        d['DS_Invert'] = invert
        d['Number_of'] = 1
        d['EntryC_or_WSa'] = 0.5
        d['ExitC_or_WSb'] = 1.0
        return d

    def map_tab_attributes(self, field_map: dict, unit: 'BridgeHandler', hwpath: Path, tabpath: Path) -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Source'] = Path(os.path.relpath(hwpath, tabpath.parent)).as_posix()
        d['Type'] = 'HW'
        d['Column_1'] = 'h'
        d['Column_2'] = 'w'
        return d

    def get_hw(self) -> OutputCollection:
        out_col = OutputCollection()
        self.hw_table = ArchBridge.gen_hw_table(self.parent.unit, self.parent.settings)
        out_col.append(self.get_hw_csv(0))
        return out_col

    def get_hw_csv(self, ind: int) -> Output:
        hw = Output('FILE', self.parent.unit.uid)
        hw.fpath = self.hw_fpath(self.parent.unit, ind)
        hw_table = self.get_hw_table(ind)
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.parent.dat.name}/{self.parent.unit.uid}\n')
        hw_table.to_csv(buf, index=False, lineterminator='\n', float_format='%.3f')
        hw.content = buf.getvalue()
        return hw

    def get_nwk(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.append(self.get_nwk_feature(0))
        return out_col

    def get_nwk_feature(self, ind: int) -> Output:
        nwk = Output('GIS', self.parent.unit.uid)
        nwk.fpath, nwk.lyrname = self.parent.output_gis_file('1d_nwk', 'BRIDGE')
        nwk.field_map = tuflow_empty_field_map('1d_nwk')
        nwk.geom_type = 2  # ogr.wkbLineString
        nwk.content.geom = self.channel_geom(self.parent.unit, ind)
        id_ = self.channel_id(self.parent.unit, ind)
        invert = self.channel_inv(self.parent.unit, ind)
        nwk.content.attributes = self.map_nwk_attributes(nwk.field_map, self.parent.unit, id_, invert)
        return nwk

    def get_tab(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.append(self.get_tab_feature(0))
        return out_col

    def get_tab_feature(self, ind: int) -> Output:
        tab = Output('GIS', self.parent.unit.uid)
        tab.fpath, tab.lyrname = self.parent.output_gis_file('1d_xs', 'BRIDGE')
        tab.field_map = tuflow_empty_field_map('1d_tab')
        tab.geom_type = 2  # ogr.wkbLineString (gdal may not be installed)
        tab.content.geom = self.mid_cross_section_geometry(ind)
        hwpath = self.hw_fpath(self.parent.unit, ind)
        tab.content.attributes = self.map_tab_attributes(tab.field_map, self.parent.unit, hwpath, tab.fpath)
        return tab

    def get_ecf(self, nwk: Output, tab: Output) -> Output:
        self.parent.ecf.fpath = self.parent.settings.output_dir / f'{self.parent.settings.outname}.ecf'
        self.parent.ecf.content = 'Read GIS Network == {0}'.format(
            self.parent.output_gis_ref(
                Path(os.path.relpath(nwk.fpath, self.parent.ecf.fpath.parent)).as_posix(),
                nwk.lyrname
            )
        )
        self.parent.ecf.content = '{0}\nRead GIS Table Links == {1}'.format(
            self.parent.ecf.content,
            self.parent.output_gis_ref(
                Path(os.path.relpath(tab.fpath, self.parent.ecf.fpath.parent)).as_posix(),
                tab.lyrname
            )
        )
        return self.parent.ecf

    def channel_geom(self, unit: 'BridgeHandler', ind: int) -> str:
        return self.parent.channel_geom(unit)

    def channel_id(self, unit: 'BridgeHandler', ind: int) -> str:
        return unit.uid

    def channel_inv(self, unit: 'BridgeHandler', ind: int) -> float:
        return unit.bed_level

    def hw_fpath(self, unit: 'BridgeHandler', ind: int) -> Path:
        return self.parent.settings.output_dir / 'csv' / f'{unit.uid}.csv'

    def get_hw_table(self, ind: int) -> pd.DataFrame:
        return self.hw_table

    def mid_cross_section_geometry(self, ind: int) -> str:
        return self.parent.mid_cross_section_geometry(self.parent.unit)


class ICulvMulti(ICulv):

    def __init__(self, parent: ArchBridge) -> None:
        super().__init__(parent)
        self.hw_tables = []
        self.channel_geoms = []

    def get_hw(self) -> OutputCollection:
        out_col = OutputCollection()
        self.hw_tables = ArchBridge.gen_hw_table(self.parent.unit, self.parent.settings)
        for i in range(self.parent.unit.arches.shape[0]):
            out_col.append(self.get_hw_csv(i))
        return out_col

    def get_nwk(self) -> OutputCollection:
        out_col = OutputCollection()
        for i in range(self.parent.unit.arches.shape[0]):
            out_col.append(self.get_nwk_feature(i))
        return out_col

    def get_tab(self) -> OutputCollection:
        out_col = OutputCollection()
        for i in range(self.parent.unit.arches.shape[0]):
            out_col.append(self.get_tab_feature(i))
        return out_col

    def channel_geom(self, unit: 'BridgeHandler', ind: int) -> str:
        if ind == 0:
            chan_geom = self.parent.channel_geom(unit)
        else:
            chan_geom = self.parent.side_channel_geom(unit, ind * 15)
        self.channel_geoms.append(chan_geom)
        return chan_geom

    def channel_id(self, unit: 'BridgeHandler', ind: int) -> str:
        if self.parent.unit.arches.shape[0] == 1:
            return super().channel_id(unit, ind)
        return f'{unit.uid}_{ind+1}'

    def channel_inv(self, unit: 'BridgeHandler', ind: int) -> float:
        return self.hw_tables[ind].h.min()

    def hw_fpath(self, unit: 'BridgeHandler', ind: int) -> Path:
        if self.parent.unit.arches.shape[0] == 1:
            return super().hw_fpath(unit, ind)
        return self.parent.settings.output_dir / 'csv' / f'{unit.uid}_{ind+1}.csv'

    def get_hw_table(self, ind: int) -> pd.DataFrame:
        return self.hw_tables[ind]

    def mid_cross_section_geometry(self, ind: int) -> str:
        if ind > 0:
            line = Line.from_wkt(self.channel_geoms[ind])
            line = line[1].to_wkt()
        else:
            line = self.channel_geoms[0]
        return self.parent.mid_cross_section_geometry(self.parent.unit, line)
