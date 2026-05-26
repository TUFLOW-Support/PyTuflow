import logging
import json
import os
import re
from pathlib import Path
from typing import TextIO
from collections import OrderedDict
import typing

import numpy as np


from ..helpers.linker import Linker
from ..helpers.prog_bar import ProgBar
from .unit_handler_manager import UnitHandlerManager
from .units.handler import Handler, Link
from ..fm_to_estry_types import PathLike
from ..helpers.reader import unpack_fixed_field
from ..helpers.settings import get_fm2estry_settings
from ..._tmf.tfpathlib import TuflowPath


if typing.TYPE_CHECKING:
    from .gxy import GXY

logger = logging.getLogger('pytuflow')
with (Path(__file__).parents[1] / 'data' / 'fm_units.json').open() as f:
    ALL_UNITS = json.loads(f.read())


class DAT:
    """Class for loading Flood Modeller dat files. This class uses a modular approach for parsing the different
     units within the dat file. Custom unit handlers can be added by subclassing the :code:`Handler` class
     and placing the new handler in :code:`parsers/units` directory.
    """

    def __init__(self, fpath: PathLike, callback: typing.Callable = None) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            Path to the dat file.
        callback : typing.Callable, optional
            A callback function to report progress, by default None. Useful if using the dat file as part of a larger
            utility or toolbox where it's nice to report the progress.
        """
        #: Path: Path to the dat file.
        self.fpath = Path(fpath)
        #: str: Name of the dat file (with ext).
        self.name = self.fpath.name
        #: str: Name of the dat file (without ext).
        self.stem = self.fpath.stem
        #: Settings: Settings object used when converting the DAT file to ESTRY.
        self.settings = get_fm2estry_settings()
        self.settings.dat_fpath = self.fpath
        #: list[Link]: List of links between units.
        self.links = []
        self._size = 0
        self._links = {}
        self._hnd_manager = UnitHandlerManager()
        self._units_id = OrderedDict()
        self._units_uid = OrderedDict()
        self._units_order = OrderedDict()
        self._fixed_field_length = self.fixed_field_length()
        self._started = False
        self._finished = False
        self._ind = -1
        self._junction_connections = {}
        self._laterals = None
        self._qtbdys = None
        self._link_id = 0
        self._line_no = 0
        self._handler2loaded = {}
        self._gxy = None
        self._callback = callback
        self._cur_prog = 0
        self._prog_bar = ProgBar(self._callback)
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<DAT {self.fpath.stem}>'
        return '<DAT>'

    @property
    def units(self) -> list[Handler]:
        #: list[Handler]: List of all units in the dat file.
        return list(self._units_order.values())

    @property
    def callback(self) -> typing.Callable:
        #: typing.Callable: Callback function to report progress.
        return self._callback

    @callback.setter
    def callback(self, callback: typing.Callable) -> None:
        self._callback = callback
        self._prog_bar.callback = callback

    def fixed_field_length(self) -> int:
        """Get the fixed field length of unit labels in the dat file.

        Returns
        -------
        int
            Fixed field length of unit labels.
        """
        fixed_field_length = 12  # default to latest
        try:
            with self.fpath.open() as fo:
                for line in fo:
                    if '#REVISION#' in line:
                        line = fo.readline()
                        header = unpack_fixed_field(line, [10] * 7)
                        self._size = int(header[0])
                        if len(header) >= 6:
                            fixed_field_length = int(header[5])
                        break
        except IOError:
            pass
        except ValueError:
            pass
        except Exception:
            pass

        return fixed_field_length

    def add_unit(self, unit: Handler) -> None:
        """Add a unit to the dat class. Called automatically as the DAT file is loaded.

        Parameters
        ----------
        unit : Handler
            A unit handler object.
        """
        if not unit:
            return
        if unit.type == 'COMMENT':
            return
        self._ind += 1
        if not unit.valid:
            unit.id = f'{unit.type}_{self._ind}'
            unit.uid = unit.id
        if unit.__class__ not in self._handler2loaded:
            self._handler2loaded[unit.__class__] = []
        self._handler2loaded[unit.__class__].append(unit)
        self._units_uid[unit.uid] = unit
        if unit.id in self._units_id:
            self._units_id[unit.id].append(unit)
        else:
            self._units_id[unit.id] = [unit]
        self._units_order[self._ind] = unit
        unit.idx = self._ind

    def unit(self, id: str, default: typing.Any = None) -> typing.Union[Handler, list[Handler]]:
        """Find the unit by its ID or UID. If an ID is passed, the return type will be a list of found units.
        If a UID is passed, a single unit will be returned. If nothing is found, the default parameter is returned.

        Parameters
        ----------
        id : str
            ID or UID of the unit.
        default : typing.Any, optional
            Default value to return if the unit is not found, by default None.

        Returns
        -------
        typing.Union[Handler, list[Handler]]
            Found unit(s) or default value.
        """
        if id in self._units_id:
            return self._units_id[id]
        if id in self._units_uid:
            return self._units_uid[id]
        return default

    def link(self, id: int) -> Link:
        """Return a link by its ID.

        Parameters
        ----------
        id : int
            ID of the link.

        Returns
        -------
        Link
            Link object.
        """
        return self.links[id - 1]

    def unit_ids(self, valid_only: bool = True) -> list[str]:
        """Return a list of unit IDs.

        Parameters
        ----------
        valid_only : bool, optional
            If True, only return valid units, by default True. Valid units are those that have a custom parser and
            not a Comment.

        Returns
        -------
        list[str]
            List of unit IDs.
        """
        if valid_only:
            return [k for k, v in self._units_id.items() if [x for x in v if x.valid]]
        return list(self._units_id.keys())

    def unit_uids(self, valid_only: bool = True) -> list[str]:
        """Return a list of unit UIDs.

        Parameters
        ----------
        valid_only : bool, optional
            If True, only return valid units, by default True. Valid units are those that have a custom parser and
            not a Comment.

        Returns
        -------
        list[str]
            List of unit UIDs.
        """
        if valid_only:
            return [k for k, v in self._units_uid.items() if v.valid]
        return list(self._units_uid.keys())

    def find_units(self, handler: typing.Union[str, Handler.__class__] = None, sub_type = '') -> list[Handler]:
        """Returns a list of units based on the Handler class e.g. 'River' will return all units loaded by the
        River Handler.

        Parameters
        ----------
        handler : typing.Union[str, Handler.__class__], optional
            Handler class or name of the Handler class to filter units by, by default None.
            If None, all units are returned.
        sub_type : str, optional
            Sub type of the unit to filter by, by default ''.

        Returns
        -------
        list[Handler]
            List of units.
        """
        if not handler:
            return list(self._units_uid.values())
        if isinstance(handler, str):
            handler = self._hnd_manager.handler_from_name(handler)
        for unit in self._handler2loaded.get(handler, ()):
            if not sub_type or sub_type.lower() == unit.sub_type.lower():
                yield unit

    def is_unit(self, line: str) -> str:
        """Check if a line is the start of a unit definition. Used automatically when loading the dat file. This
        method is only used if a custom handler is not found for the unit.

        Parameters
        ----------
        line : str
            Line from the dat file.

        Returns
        -------
        str
            Unit type if the line is the start of a unit definition, else an empty string.
        """
        for unit in ALL_UNITS:
            if line.startswith(unit):
                return unit
        return ''

    def load(self) -> None:
        """Load the dat file. This method is called automatically when the DAT object is created."""
        self.reset_progress()
        # load units into data structure
        with self.fpath.open() as f:
            while not self._started:
                self._load_header(f)
            while not self._finished:
                self._load_unit(f)

        # link units - loop through units and link them to their upstream and downstream units
        self._link_units()

        # INTERPOLATES and REPLICATES
        self._add_missing_bed_elevations()

    def add_gxy(self, gxy: 'GXY') -> None:
        """Adds GXY object to the DAT object. This effectively adds geo-referencing the Dat units.

        Parameters
        ----------
        gxy : GXY
            GXY object.
        """
        self.reset_progress()
        size = len(self.units) * 2 - 1
        self._gxy = gxy
        for unit in self.units:
            if unit.uid in gxy.node_df.index:
                unit.x, unit.y = gxy.node_df.loc[unit.uid, ['x', 'y']]
                unit.wktgeom = f'POINT ({unit.x} {unit.y})'
            if self.callback:
                self._cur_prog += 1
                self._prog_bar.progress_callback(self._cur_prog, size)
        for link in self.links:
            if link.ups_unit.wktgeom and link.dns_unit.wktgeom:
                link.wktgeom = f'LINESTRING ({link.ups_unit.x} {link.ups_unit.y}, {link.dns_unit.x} {link.dns_unit.y})'
            if self.callback:
                self._cur_prog += 1
                self._prog_bar.progress_callback(self._cur_prog, size)

    def write_check(self) -> None:
        """Writes the DAT file to a GIS layer. The :code:`self.settings` object is used to determine the output
        format and location.
        """
        node_fields = OrderedDict({
            'uid': {'type': 'str', 'width': 50},
            'dx': {'type': 'float'},
            'bed_level': {'type': 'float'},
        })
        link_fields = OrderedDict({
            'id': {'type': 'int'},
        })
        crs = self.settings.crs_ if self.settings.crs_ is not None else self.settings.crs

        if not self.settings.group_db or self.settings.gis_format != 'GPKG':
            dbfnode = self.settings.output_dir / f'{self.fpath.stem}_check_nodes{self.settings.gis_ext_}'
            dbflink = self.settings.output_dir / f'{self.fpath.stem}_check_links{self.settings.gis_ext_}'
            node_lyrname = dbfnode.stem
            link_lyrname = dbflink.stem
        else:
            dbfpath = self.settings.output_dir / f'{self.fpath.stem}_check{self.settings.gis_ext_}'
            dbfnode = dbfpath
            dbflink = dbfpath
            node_lyrname = 'nodes'
            link_lyrname = 'links'

        node_vlo = TuflowPath(f'{dbfnode} >> {node_lyrname}').open_gis('w', geometry_type='Point', crs=crs)
        for name, info in node_fields.items():
            node_vlo.create_field(name, info['type'], width=info.get('width'))
        link_vlo = TuflowPath(f'{dbflink} >> {link_lyrname}').open_gis('w', geometry_type='LineString', crs=crs)
        for name, info in link_fields.items():
            link_vlo.create_field(name, info['type'], width=info.get('width'))

        for unit in self.units:
            unit.write_check(node_vlo)
        for link in self.links:
            link.write_check(link_vlo)
        node_vlo.close()
        link_vlo.close()

    def connected_to_junction(self, unit: Handler) -> list[Handler]:
        """Returns whether the unit is connected to a junction unit.

        Parameters
        ----------
        unit : Handler
            Unit to check.

        Returns
        -------
        list[Handler]
            List of junction units that are connected to unit.
        """
        if unit.type in ['JUNCTION', 'RESERVOIR']:
            return []
        if not self._junction_connections:
            self._populate_junction_connections()
        return self._junction_connections.get(unit.id, [])

    def lat_from_lat_conn_id(self, lateral_id: str) -> Handler:
        """Returns the lateral unit from a lateral connection ID.

        Parameters
        ----------
        lateral_id : str
            Lateral connection ID.

        Returns
        -------
        Handler
            Lateral unit.
        """
        if self._laterals is None:
            self._populate_laterals()
        for lat_unit in self._laterals:
            if lateral_id in lat_unit.unit_labels:
                return lat_unit

    def lat_from_lat_conn_id_node(self, lateral_id: str) -> Handler:
        """Returns the lateral unit from a lateral node connection ID. It is assumed that these are QT boundaries
        and not lateral inflow units.

        Parameters
        ----------
        lateral_id : str
            Lateral node connection ID.

        Returns
        -------
        Handler
            QTBDY unit.
        """
        if self._qtbdys is None:
            self._populate_qtbdys()
        for lat_unit in self._qtbdys:
            if lateral_id.lower() == lat_unit.id.lower():
                return lat_unit

    def reset_progress(self) -> None:
        """Reset the progress bar. Only required if using the callback functionality."""
        self._cur_prog = 0
        self._prog_bar.reset()
        if self.callback and self._size:
            self.callback(0)

    def _link_unit(self, ups_unit: Handler, dns_unit: Handler) -> None:
        link = Link(-1, ups_unit, dns_unit)
        if link in self._links:
            return
        self._link_id += 1
        link = Link(self._link_id, ups_unit, dns_unit)
        self.links.append(link)
        self._links[link] = link  # hash version of link list, so it can be checked against easily/quickly
        ups_unit.dns_units.append(dns_unit)
        ups_unit.dns_link_ids.append(self._link_id)
        dns_unit.ups_units.append(ups_unit)
        dns_unit.ups_link_ids.append(self._link_id)

    def _link_units(self) -> None:
        self.start_new = True
        for unit in self._units_order.values():
            unit_linker = Linker(unit)
            if unit_linker.skip():
                continue
            for dns_unit in unit_linker.downstream_links():
                self._link_unit(unit, dns_unit)
            for ups_unit in unit_linker.upstream_links():
                self._link_unit(ups_unit, unit)
            self.start_new = unit_linker.start_new()

    def _add_missing_bed_elevations(self) -> None:
        for unit in self.units:
            if unit.unit_type_name() == 'REPLICATE' and not unit.populated:
                ups_unit = None
                ups_units = unit.ups_units
                while ups_units and ups_units[0].type == 'REPLICATE' and not ups_units[0].populated:
                    ups_unit = ups_units[0]
                    ups_units = ups_unit.ups_units
                if not ups_unit and not ups_units:
                    continue
                if not ups_unit:
                    ups_unit = ups_units[0]
                # replicate
                unit_ = ups_unit.dns_units[0]
                while unit_.uid != unit.uid:
                    unit_.bed_level = ups_unit.bed_level - unit_.dz
                    unit_.populated = True
                    ups_unit = unit_
                    unit_ = unit_.dns_units[0]
                unit.bed_level = ups_unit.bed_level - unit.dz
                unit.populated = True
        for unit in self.units:
            if unit.unit_type_name() == 'INTERPOLATE' and not unit.populated:
                # upstream
                ups_unit = None
                ups_units, dns_units = unit.ups_units, unit.dns_units
                us_len, ds_len = 0., unit.dx
                while ups_units and ups_units[0].type == 'INTERPOLATE' and not ups_units[0].populated:
                    ups_unit = ups_units[0]
                    us_len += ups_unit.dx
                    ups_units = ups_units[0].ups_units
                if not ups_unit and not ups_units:
                    continue
                if not ups_unit:
                    ups_unit = ups_units[0]
                    us_len = ups_unit.dx

                # downstream
                while dns_units and dns_units[0].type == 'INTERPOLATE' and not dns_units[0].populated:
                    ds_len += dns_units[0].dx
                    dns_units = dns_units[0].dns_units
                if not dns_units:
                    continue
                dns_unit = dns_units[0]

                # interpolate
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
            if unit.TYPE == 'junction':
                for conn in unit.connections:
                    if conn not in self._junction_connections:
                        self._junction_connections[conn] = []
                    self._junction_connections[conn].append(unit)

    def _populate_laterals(self) -> None:
        self._laterals = [x for x in self._units_order.values() if x.type == 'LATERAL']

    def _populate_qtbdys(self) -> None:
        self._qtbdys = [x for x in self._units_order.values() if x.type == 'QTBDY']

    def _load_header(self, fo: TextIO) -> None:
        for line in fo:
            self._line_no += 1
            if line.startswith('END GENERAL'):
                self._started = True
            return
        self._finished = True

    def _load_unit(self, fo: TextIO) -> None:
        for line in fo:
            self._line_no += 1
            if re.findall(r'^(GISINFO|INITIAL CONDITIONS)', line):
                break
            unit = self._hnd_manager.is_recognised_handler(line)
            if unit:
                unit.parent = self
                try:
                    unit.load(line, fo, self._fixed_field_length, self._line_no)
                except Exception as e:
                    logger.error(f'Uncaught error loading {unit.uid} on line {self._line_no}: {e}')
                self._line_no = unit.line_no
                self.add_unit(unit)
                if unit.TYPE not in ['boundary', 'hydrology']:
                    self._cur_prog += 1
            elif self.is_unit(line):
                unit = Handler(self)  # generic base handler
                unit.type = self.is_unit(self.is_unit(line))
                self.add_unit(unit)
            if self.callback and self._size:
                self._prog_bar.progress_callback(self._cur_prog, self._size)
        self._finished = True
        if self.callback and self._size:
            self._cur_prog = self._size
            self._prog_bar.progress_callback(self._cur_prog, self._size)
