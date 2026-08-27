import io
import os
import typing
from collections import OrderedDict
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd
import numpy as np

from .bridge_pier_loss import PierLossBridge
from ..output import Output, OutputCollection
from ..helpers.geometry import generate_bridge_section, generate_bridge_losses
from ..helpers.tuflow_empty_files import tuflow_empty_field_map

if typing.TYPE_CHECKING:
    from ..parsers.units.bridge import Bridge as BridgeHandler


class USBPRBridge(PierLossBridge):

    def __init__(self, unit: 'BridgeHandler' = None) -> None:
        super().__init__(unit)
        self._piers = pd.DataFrame()
        if unit:
            self.nwk_culv = Output('GIS', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'BRIDGE_USBPR1978'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.append(self.get_nwk())
        if self.unit.nculv:
            out_col.extend(self.get_nwk_culv())
        out_col.append(self.get_xs())
        out_col.append(self.get_bg())
        out_col.extend(self.get_tab())
        out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes_culv(self, field_map: dict, unit: 'BridgeHandler', ind: int) -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        if unit.nculv == 1:
            d['ID'] = f'{unit.uid}_RELIEF_CULV'
        else:
            d['ID'] = f'{unit.uid}_RELIEF_CULV_{ind + 1}'
        d['Type'] = 'R'
        d['Len_or_ANA'] = 10
        d['n_nf_Cd'] = 0.015
        d['US_Invert'] = unit.culvs['invert'].iloc[ind]
        d['DS_Invert'] = unit.culvs['invert'].iloc[ind]
        height = unit.culvs['soffit'].iloc[ind] - unit.culvs['invert'].iloc[ind]
        d['Width_or_Dia'] = unit.culvs['area'] / height
        d['Height_or_WF'] = height
        d['Number_of'] = 1
        d['HConF_or_WC'] = 0.6
        d['WConF_or_WEx'] = 0.9
        d['EntryC_or_WSa'] = 0.5
        d['ExitC_or_WSb'] = 1.0
        return d

    def get_nwk_culv(self) -> OutputCollection:
        out_col = OutputCollection()
        for i in range(self.unit.nculv):
            nwk = Output('GIS', self.unit.uid)
            nwk.fpath, nwk.lyrname = self.output_gis_file('1d_nwk', 'CULVERT')
            if i == 0:
                self.nwk_culv.fpath = nwk.fpath
                self.nwk_culv.lyrname = nwk.lyrname
            nwk.field_map = tuflow_empty_field_map('1d_nwk')
            nwk.geom_type = 2  # ogr.wkbLineString
            nwk.content.geom = self.side_channel_geom(self.unit, (i + 1) * 15)
            nwk.content.attributes = self.map_nwk_attributes_culv(nwk.field_map, self.unit, i)
            out_col.append(nwk)
        return out_col

    def get_xs(self) -> Output:
        self.xs.fpath = self.settings.output_dir / 'csv' / f'{self.unit.uid}.csv'

        # add a 'top level' - the average of all the springing levels and soffits
        xs = self.unit.xs[['x', 'y']].copy()
        self._top_level =  float(self.unit.arches[['springing level', 'soffit']].mean().mean())
        xs['top_level'] = self._top_level

        # get left and right abutment points
        xmin = self.unit.arches.start.min()
        xmax = self.unit.arches.finish.max()
        xs.set_index('x', inplace=True)
        if xmin not in xs.index:
            xs.loc[xmin] = 0.  # avoids future warning by appending a row of zeros then changing to nan
            xs.loc[xmin] = np.nan
        if xmax not in xs.index:
            xs.loc[xmax] = 0.  # avoids future warning by appending a row of zeros then changing to nan
            xs.loc[xmax] = np.nan
        xs.sort_index(inplace=True)
        xs.interpolate(method='index', inplace=True, limit_direction='both')
        left_idx = xs.index.get_loc(xmin)
        if isinstance(left_idx, slice):
            left_idx = xs.reset_index().iloc[left_idx].y.idxmax()
        right_idx = xs.index.get_loc(xmax)
        if isinstance(right_idx, slice):
            right_idx = xs.reset_index().iloc[right_idx].y.idxmax()

        # arrange piers into the same format similar to PIERLOSS bridge
        pierw = self.unit.pierw / self.unit.npier if self.unit.npier else 0
        piers = []
        for i in range(self.unit.narch):
            arch = self.unit.arches.iloc[i]
            c = self.intermediate_arch_count(i)
            start = arch.start
            inc = (arch.finish - arch.start) / (c + 1)
            for j in range(c):
                finish = (start + inc) - pierw / 2
                next_start = finish + pierw
                piers.append([finish, arch.soffit, next_start, arch.soffit])
                start = next_start
            if i != self.unit.narch - 1:
                next_arch = self.unit.arches.iloc[i + 1]
                piers.append([arch.finish, arch.soffit, next_arch.start, next_arch.soffit])
        self._piers = pd.DataFrame(piers, columns=['xleft', 'hleft', 'xright', 'hright'])

        # generate bridge cross-section
        self._bridge_section = generate_bridge_section(xs.reset_index(drop=False), left_idx, right_idx, self._piers,
                                                       as_df=True)

        # write section to output object
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.dat.name}/{self.unit.uid}\n')
        self._bridge_section.to_csv(buf, index=False, lineterminator='\n')
        self.xs.content = buf.getvalue()
        return self.xs

    def intermediate_arch_count(self, ind: int) -> int:
        if not self.unit.npier:
            return 0
        npier = self.unit.npier // self.unit.narch
        if self.unit.npier % self.unit.narch > ind:
            npier += 1
        return npier

    def get_bg(self) -> Output:
        self.bg.fpath = self.settings.output_dir / 'csv' / f'{self.unit.uid}_bg.csv'
        bg = generate_bridge_losses(self._bridge_section, self._top_level, self._piers,
                                    None, self.unit.skewb, self.unit.shape, self.unit.diaph, self.unit.prcoef,
                                    self.unit.altype, self._piers.shape[0], as_df=True)
        bg[['lc']] = bg[['lc']] * self.unit.cali

        # write section to output object
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.dat.name}/{self.unit.uid}\n')
        bg.to_csv(buf, index=False, lineterminator='\n')
        self.bg.content = buf.getvalue()
        return self.bg

    def get_ecf(self) -> Output:
        self.ecf = super().get_ecf()
        if self.unit.nculv:
            self.ecf.content = '{0}\nRead GIS Network == {1}'.format(
                self.ecf.content,
                self.output_gis_ref(
                    Path(os.path.relpath(self.nwk_culv.fpath, self.ecf.fpath.parent)).as_posix(), self.nwk_culv.lyrname
                )
            )
        return self.ecf
