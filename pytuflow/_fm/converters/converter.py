import typing
from collections import OrderedDict
from pathlib import Path

import numpy as np

from ..output import OutputCollection
from ..helpers.settings import get_fm2estry_settings
from ..helpers.geometry import Point, Line, get_right_angle_line
from ..helpers.scanner import Scanner, ScanRule

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler
    from ..parsers.units.junction import Junction as JunctionHandler


class Converter:
    """Converter base class to be overriden by subclasses for each unit converter.
    Require overriding:
        - complete_unit_type_name() -> str: return the unittype_subtype
        - convert() -> OutputCollection: returns all outputs (using 'Output' class for text files and GIS files)
                       that are output from the conversion.
    Useful public methods that should be used in the conversion:
        - channel_geom(unit) -> str:  Returns the channel geometry (1d_nwk) for the given unit in WKT format.
        - end_channel_geom(unit) -> str: Returns the geometry (as WKT) of an end cross-section for the given unit
        - mid_channel_geom(unit) -> str: Returns the geometry (as WKT) of a mid cross-section for the given unit.
        - output_gis_file(prefix, suffix) -> str, str: Returns the output gis file path and layer name given the
                                                       global settings.
        - output_gis_ref(db, lyrname) -> str: Returns the GIS file reference for the control file command
        - get_ups_unit(unit) -> unit: Returns the first real upstream unit from the given unit
        - get_dns_unit(unit) -> unit: Returns the first real downstream unit from the given unit
        - get_ups_node(unit) -> unit: Returns the upstream unit for GIS purposes
        - get_dns_node(unit) -> unit: Returns the downstream unit for GIS purposes
        - dist_between_units -> float: Returns the distance between two units (must be a unit containing dx property)
    """

    def __init__(self, unit: 'Handler' = None, *args, **kwargs) -> None:
        self.unit = unit
        self.parent = None
        if self.unit:
            self.dat = unit.parent
        self.settings = get_fm2estry_settings()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} ({self.complete_unit_type_name()}>'

    @staticmethod
    def complete_unit_type_name() -> str:
        # must override
        return ''

    def convert(self) -> OutputCollection:
        """Must override"""
        return OutputCollection()

    def channel_geom(self, unit: 'Handles') -> str:
        """Returns channel geometry (1d_nwk)
        connect_nodes = the unit is a River or Conduit which uses at least 2 units and finishes when dx = 0
        node_as_channel = the unit is a single node that connects the upstream and downstream units.

        If an upstream/downstream unit is a junction, the channel will be extended to inlcude the junction if
        the channel is the only connection on that given end
        (e.g. if it is the only incoming connection to a junction, the downstream end of the channel will
        be extended and visa-versa for the other end of the channel and outgoing connections from a given junction.)
        """
        if self.unit.TYPE == 'unit':  # this denotes a River or Conduit that has at least 2 units
            return self._connect_nodes(unit)
        else:  # typically a 'structure' - these are represented as a single unit
            return self._node_as_channel(unit)

    def side_channel_geom(self, unit: 'Handler', offset: float) -> str:
        def offset_position_at_distance_along_line(line: Line, dist: float, offset: float) -> Point:
            iseg = line.segment_index(dist)
            normal_line = get_right_angle_line(line[iseg], line.position_along_line(dist), abs(offset * 2), False)
            return normal_line.points[-1] if offset >= 0 else normal_line.points[0]

        orig_line = Line.from_wkt(self.channel_geom(unit))
        p1 = orig_line.points[0]  # first point of return line

        line = Line(points=[orig_line.points[0], orig_line.points[-1]])  # line from just first and last vertex
        p2 = offset_position_at_distance_along_line(line, line.length() / 3., offset)
        p3 = offset_position_at_distance_along_line(line, line.length() * 2. / 3., offset)
        p4 = orig_line.points[-1]  # last point of return line

        return Line(points=[p1, p2, p3, p4]).to_wkt()

    def output_gis_file(self, prefix: str, suffix: str) -> tuple[str, str]:
        """Returns the output GIS fpath and layer name (there can be different for GPKG)
        prefix: tuflow type (e.g. 1d_nwk)
        suffix: unique identifier for the GIS layer e.g. RIVER, or CONDUIT
        """
        lyr = f'{prefix}'
        if suffix and self._use_suffix(prefix):  # suffix is ignored if the user has chosen to output all to a single GIS
            lyr = f'{lyr}_{suffix}'
        lyr = f'{lyr}_{self.settings.outname}'
        if self.settings.group_db and self.settings.gis_format == 'GPKG':
            db = self.settings.output_dir / 'gis' / f'{self.settings.outname}{self.settings.gis_ext_}'
        else:
            db = self.settings.output_dir / 'gis' / f'{lyr}{self.settings.gis_ext_}'
        return db, lyr

    def output_gis_ref(self, db: str, lyr: str) -> str:
        """Output GIS file reference for TUFLOW command."""
        if self.settings.group_db:
            return f'{lyr}'
        if Path(db).stem.lower() == lyr.lower():
            return db
        return f'{db} >> {lyr}'

    def end_cross_section_geom(self, unit: 'Handler', avg_with_ups: bool = False) -> str:
        """Returns end cross-section geometry.
        Will consider whether the cross-section end is on a junction or not (see 'channel_geom' method for explanation).
        """
        snapping = 'end only'
        if self.unit.dx > 0:
            line = Line.from_wkt(self.channel_geom(unit))
            point = line.points[0]
            if avg_with_ups and unit.ups_units and unit.ups_units[0].TYPE == 'unit':
                ups_line = Line.from_wkt(self.channel_geom(unit.ups_units[0]))
                line = Line(points=ups_line.points + line.points[1:])
                snapping = 'mid_only'
        else:
            line = Line.from_wkt(self.channel_geom(unit.ups_units[0]))
            point = line.points[-1]
        return get_right_angle_line(line, point, self.settings.xs_gis_length, True,
                                    snapping=snapping).to_wkt()

    def mid_cross_section_geometry(self, unit: 'Handler', line: Line = None, loc: float = 0.5) -> str:
        """Returns mid cross-section geometry.
        Will consider whether the cross-section end is on a junction or not (see 'channel_geom' method for explanation).
        """
        if line and isinstance(line, str):
            line = Line.from_wkt(line)
        else:
            line = Line.from_wkt(self.channel_geom(unit))
        return get_right_angle_line(line, line.position_along_line(line.length() * loc),
                                    self.settings.xs_gis_length, False, atol=2.,
                                    snapping='mid_only').to_wkt()

    def get_ups_unit(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        """First actual upstream unit.
        Will skip unit types listed in "skip" and keep going upstream. Skip units can also be a sequence of types. The
        start of the sequence will be checked starting at the current unit.
        "check_first" will return the original unit if it is valid otherwise will return first upstream unit.
        """
        scanner = Scanner()
        rules = [
            ScanRule('INTERPOLATE'),
            ScanRule('REPLICATE'),
            ScanRule('JUNCTION'),
            ScanRule('BLOCKAGE'),
            ScanRule(('RIVER', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_INLET')),
            ScanRule(('CONDUIT', 'ORIFICE')),
        ]
        excl_first = True
        if not consider_self and unit.ups_units and unit.ups_units[0].type == unit.type:
            excl_first = False
        return scanner.scan(unit, 'upstream', rules, consider_self, excl_first, True)

    def get_dns_unit(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        """First actual downstream unit.
        Will skip unit types listed in "skip" and keep going downstream. Skip units can also be a sequence of types. The
        start of the sequence will be checked starting at the current unit.
        "check_first" will return the original unit if it is valid otherwise will return first downstream unit.
        """
        scanner = Scanner()
        rules = [
            ScanRule('INTERPOLATE'),
            ScanRule('REPLICATE'),
            ScanRule('JUNCTION'),
            ScanRule('BLOCKAGE'),
            ScanRule(('RIVER', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_OUTLET')),
        ]
        excl_first = True
        if not consider_self and unit.dns_units and unit.dns_units[0].type == unit.type:
            excl_first = False
        return scanner.scan(unit, 'downstream', rules, consider_self, excl_first, True)

    def get_ups_node(self, unit: 'Handler', consider_self: bool) -> 'Handler':
        """Returns upstream node for GIS purposes"""
        scanner = Scanner()
        rules = [
            ScanRule('BLOCKAGE'),
            ScanRule(('RIVER', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_INLET')),
            ScanRule(('CONDUIT', 'ORIFICE')),
        ]
        ups_node = scanner.scan(unit, 'upstream', rules, consider_self, True, False)
        return self._consider_ups_junction(ups_node, ups_node)

    def get_dns_node(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        """Returns downstream node for GIS purposes"""
        scanner = Scanner()
        rules = [
            ScanRule('BLOCKAGE'),
            ScanRule(('RIVER', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_BEND')),
            ScanRule(('CONDUIT', 'CULVERT_OUTLET')),
        ]
        dns_node = scanner.scan(unit, 'downstream', rules, consider_self, True, False)
        return self._consider_dns_junction(dns_node, dns_node)

    def dist_between_units(self, first_unit: 'Handler', second_unit: 'Handler') -> float:
        """Units must be RIVER, CONDUIT, REPLICATE, or INTERPOLATE."""
        dx = first_unit.dx
        dns_unit = first_unit.dns_units[0]
        while dns_unit.uid != second_unit.uid:
            dx += dns_unit.dx
            dns_unit = dns_unit.dns_units[0]
        return dx

    def _consider_ups_junction(self, unit: 'Handler', return_unit: 'Handler') -> 'Handler':
        from .junction import Junction
        if unit.ups_units and unit.ups_units[0].TYPE == 'junction':
            junc_unit = unit.ups_units[0]
            junc_ = Junction(junc_unit)
            if len(junc_.dns_connections()) == 1 and junc_.ups_connections():
                return junc_unit
        return return_unit

    def _consider_dns_junction(self, unit: 'Handler', return_unit: 'Handler') -> 'Handler':
        from .junction import Junction
        if unit.dns_units and unit.dns_units[0].TYPE == 'junction':
            junc_unit = unit.dns_units[0]
            junc_ = Junction(junc_unit)
            if len(junc_.ups_connections()) == 1 and junc_.dns_connections():
                return junc_unit
        return return_unit

    def _use_suffix(self, prefix: str) -> bool:
        return not (prefix == '1d_nwk' and self.settings.single_nwk) and \
            not (prefix in ['1d_xs', '1d_hw', '1d_tab'] and self.settings.single_tab)

    def _connect_nodes(self, unit: 'Handler') -> str:
        ups_node = self.get_ups_node(unit, True)
        dns_node = self.get_dns_node(unit, False)
        nodes = self._walk_nodes(ups_node, dns_node)
        return Line(points=[Point(node.x, node.y) for node in nodes]).to_wkt()

    def _node_as_channel(self, unit: 'Handler') -> str:
        return Line(
            points=[
                Point(self.get_ups_node(unit, False).x, self.get_ups_node(unit, False).y),
                Point(unit.x, unit.y),
                Point(self.get_dns_node(unit).x, self.get_dns_node(unit).y)
            ]
        ).to_wkt()

    def _walk_nodes(self, ups_node: 'Handler', dns_node: 'Handler') -> list['Handler']:
        nodes = [ups_node]
        _ = self._walk_downstream(ups_node, dns_node, nodes)
        return nodes

    def _walk_downstream(self, node: 'Handler', dns_node: 'Handler', nodes: list['Handler']) -> bool:
        for nd in node.dns_units:
            nodes.append(nd)
            if nd.uid == dns_node.uid:
                return True
            nodes_ = []
            found = self._walk_downstream(nd, dns_node, nodes_)
            if found:
                nodes.extend(nodes_)
                return True
            else:
                nodes.pop()
        return False
