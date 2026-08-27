import json
import re
from pathlib import Path
from typing import TextIO
from collections import OrderedDict

try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .fm_unit_handler import Handler
from ...utils.unpack_fixed_field import unpack_fixed_field
from ...tmf_types import PathLike


with (Path(__file__).parents[2] / 'data' / 'fm_units.json').open() as f:
    ALL_UNITS = json.loads(f.read())


class Link:

    def __init__(self, id_: int, ups_unit: Handler, dns_unit: Handler) -> None:
        self.id = id_
        self.ups_unit = ups_unit
        self.dns_unit = dns_unit

    def __repr__(self) -> str:
        return f'<Link {self.id} {self.ups_unit.uid} -> {self.dns_unit.uid}>'


# noinspection DuplicatedCode
class Dat:

    def __init__(self) -> None:
        self.fpath = None
        self._units_id = OrderedDict()
        self._units_uid = OrderedDict()
        self._units_order = OrderedDict()
        self._fixed_field_length = self.fixed_field_length()
        self._started = False
        self._finished = False
        self._ind = -1
        self._junction_connections = {}
        self._link_id = 0
        self.links = []
        self.handlers = []
        self.handler2loaded = {}
        self.load_errors = {'unknown id': []}
        self.add_handler(Handler)  # add generic handler

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<DAT {self.fpath.stem}>'
        return '<DAT>'

    def fixed_field_length(self) -> int:
        fixed_field_length = 12  # default to latest
        try:
            with self.fpath.open() as fo:
                for line in fo:
                    if '#REVISION#' in line:
                        line = fo.readline()
                        header = unpack_fixed_field(line, [10] * 7)
                        if len(header) >= 6:
                            fixed_field_length = int(header[5])
                        break
        except IOError:
            pass
        except ValueError:
            pass
        except AttributeError:
            pass

        return fixed_field_length

    def add_handler(self, handler: type[Handler]):
        h = handler()
        self.handlers.append(h)
        self.handler2loaded[handler] = []

    def add_unit(self, unit: Handler | None):
        self._ind += 1
        if not unit:
            return
        if not unit.valid:
            unit.id = f'{unit.keyword}_{self._ind}'
            unit.uid = unit.id
        self.handler2loaded[unit.__class__].append(unit)
        self._units_uid[unit.uid] = unit
        if unit.id in self._units_id:
            self._units_id[unit.id].append(unit)
        else:
            self._units_id[unit.id] = [unit]
        self._units_order[self._ind] = unit

    def unit(self, id_: str) -> list[Handler]:
        if id_ in self._units_id:
            return self._units_id[id_]
        if id_ in self._units_uid:
            return self._units_uid[id_]
        raise KeyError(f'Unit with id {id_} not found in the model.')

    def unit_ids(self, valid_only: bool = True) -> list[str]:
        if valid_only:
            return [k for k, v in self._units_id.items() if [x for x in v if x.valid]]
        return list(self._units_id.keys())

    def unit_uids(self, valid_only: bool = True) -> list[str]:
        if valid_only:
            return [k for k, v in self._units_uid.items() if v.valid]
        return list(self._units_uid.keys())

    def units(self, handler: type[Handler] = None) -> list[Handler]:
        if not handler:
            return list(self._units_uid.values())
        return self.handler2loaded[handler]

    @staticmethod
    def is_unit(line: str) -> str:
        for unit in ALL_UNITS:
            if line.startswith(unit):
                return unit
        return ''

    def is_recognised_handler(self, line: str) -> Handler | None:
        for handler in self.handlers:
            if handler.valid:
                if line.startswith(handler.keyword):
                    return handler.__class__()
        return None

    def handler_from_name(self, name: str) -> type[Handler] | None:
        for handler in self.handlers:
            if handler.__class__.__name__.lower() == name.lower():
                return handler.__class__
        return None

    def load(self, fpath: PathLike) -> None:
        # load units into data structure
        self.fpath = Path(fpath)
        with self.fpath.open() as f:
            while not self._started:
                self._load_header(f)
            while not self._finished:
                self._load_unit(f)

        # link units - loop through units and link them to their upstream and downstream units
        # self._link_units()

        # remove junctions (record junction in another property)
        # but for upstream/downstream connections, use the junction's connections
        # self._remove_junctions()

        # self._add_missing_bed_elevations()  # INTERPOLATES and REPLICATES

    def connected_to_junction(self, unit: Handler) -> list[int]:
        if unit.keyword in ['JUNCTION', 'RESERVOIR']:
            return []
        if not self._junction_connections:
            self._populate_junction_connections()
        inds = []
        for ind, connections in self._junction_connections.items():
            if unit.id in connections:
                inds.append(ind)
        return inds

    def _link_unit(self, ups_unit: Handler, dns_unit: Handler):
        self._link_id += 1
        link = Link(self._link_id, ups_unit, dns_unit)
        self.links.append(link)
        ups_unit.dns_units.append(dns_unit)
        ups_unit.dns_link_ids.append(self._link_id)
        dns_unit.ups_units.append(ups_unit)
        dns_unit.ups_link_ids.append(self._link_id)

    def _link_units(self) -> None:
        start_new = True  # beginning of a new branch
        for ind, unit in self._units_order.items():
            if unit.type == 'junction':
                continue
            ds_unit = None
            inds = self.connected_to_junction(unit)
            if inds:  # connected to a junction
                for ind_ in inds:
                    junc_unit = self._units_order[ind_]
                    if unit.ups_units or start_new or (hasattr(unit, 'dns_label') and unit.dns_label in junc_unit.connections and unit.ups_label not in junc_unit.connections):  # junction is downstream
                        ds_unit = junc_unit
                        self._link_unit(unit, ds_unit)
                    else:  # junction is upstream
                        us_unit = junc_unit
                        self._link_unit(us_unit, unit)
            if not ds_unit and (not start_new and unit.type != 'boundary'):
                if hasattr(unit, 'dns_label'):
                    ds_units = self.unit(unit.dns_label)
                    if ds_units:
                        ds_unit = ds_units[0]
                    else:
                        for junc in self.units(self.handler_from_name('Junction')):
                            if unit.dns_label in junc.connections:
                                ds_unit = junc
                                break
                else:
                    ds_ind = ind + 1
                    if ds_ind in self._units_order:
                        ds_unit = self._units_order[ds_ind]
                if ds_unit:
                    self._link_unit(unit, ds_unit)

            if hasattr(unit, 'spill_1') and unit.spill_1:
                id_ = unit.spill_1
                if id_ in self._units_id:
                    for unit_ in self._units_id[id_]:
                        if unit_.keyword == 'SPILL':
                            self._link_unit(unit, unit_)
            if hasattr(unit, 'spill_2') and unit.spill_2:
                id_ = unit.spill_2
                if id_ in self._units_id:
                    for unit_ in self._units_id[id_]:
                        if unit_.keyword == 'SPILL':
                            self._link_unit(unit, unit_)

            if start_new:
                start_new = False
            elif unit.type == 'boundary':
                start_new = True  # boundary terminates a chain of units

    def _add_missing_bed_elevations(self) -> None:
        for unit in self.units():
            if unit.keyword == 'REPLICATE' and not unit.populated:
                ups_units = unit.ups_units
                while ups_units and ups_units[0].keyword == 'REPLICATE' and not ups_units[0].populated:
                    ups_units = ups_units[0].ups_units
                ups_unit = ups_units[0]
                unit_ = ups_unit.dns_units[0]
                while unit_.uid != unit.uid:
                    unit_.bed_level = ups_unit.bed_level - unit_.dz
                    unit_.populated = True
                    ups_unit = unit_
                    unit_ = unit_.dns_units[0]
                unit.bed_level = ups_unit.bed_level - unit.dz
                unit.populated = True
        for unit in self.units():
            if unit.keyword == 'INTERPOLATE' and not unit.populated:
                ups_units, dns_units = unit.ups_units, unit.dns_units
                us_len, ds_len = 0., unit.dx
                while ups_units and ups_units[0].keyword == 'INTERPOLATE' and not ups_units[0].populated:
                    ups_units = ups_units[0].ups_units
                    us_len += ups_units[0].dx
                if not ups_units:
                    continue
                ups_unit = ups_units[0]
                us_len += ups_units[0].dx
                while dns_units and dns_units[0].keyword == 'INTERPOLATE' and not dns_units[0].populated:
                    ds_len += dns_units[0].dx
                    dns_units = dns_units[0].dns_units
                if not dns_units:
                    continue
                dns_unit = dns_units[0]
                slope = (ups_unit.bed_level - dns_unit.bed_level) / (us_len + ds_len)
                unit_ = ups_unit.dns_units[0]
                dx = ups_unit.dx
                while unit_.uid != dns_unit.uid:
                    unit_.bed_level = ups_unit.bed_level - slope * dx
                    unit_.populated = True
                    dx += unit_.dx
                    unit_ = unit_.dns_units[0]

    def _populate_junction_connections(self) -> None:
        for ind, unit in self._units_order.items():
            if unit.keyword == 'JUNCTION':
                self._junction_connections[ind] = unit.connections

    def _load_header(self, fo: TextIO) -> None:
        for line in fo:
            if line.startswith('END GENERAL'):
                self._started = True
            return
        self._finished = True

    def _load_unit(self, fo: TextIO) -> None:
        for line in fo:
            if re.findall(r'^(GISINFO|INITIAL CONDITIONS)', line):
                break
            handler = self.is_recognised_handler(line)
            if handler:
                try:
                    buf = handler.load(line, fo, self._fixed_field_length)
                except NotImplementedError:
                    # could be a subunit type that is not supported (e.g. RIVER_MUSKINGUM)
                    self.add_unit(None)
                    return
                if buf is None:
                    return
                if handler.ncol:
                    df = pd.read_fwf(buf, widths=[10]*handler.ncol, names=handler.headers, header=None)
                else:
                    df = pd.DataFrame()
                unit = handler.post_load(df)
                self.add_unit(unit)
                return
            if self.is_unit(line):
                handler = Handler()  # generic base handler
                handler.keyword = self.is_unit(self.is_unit(line))
                self.add_unit(handler)
        self._finished = True
