from ..parsers.units.handler import Handler
from ..parsers.units.junction import Junction as JunctionHandler


class LinkHelper:

    def __init__(self, unit: Handler) -> None:
        self.unit = unit
        self.dat = self.unit.parent
        self.idx = self.unit.idx
        self.juncs = self.dat.connected_to_junction(self.unit)

    def junction_is_dns(self, junc: JunctionHandler):
        return False

    def skip(self) -> bool:
        return False

    def new_start(self):
        return False

    def no_longer_new(self) -> bool:
        return True

    def start_new(self) -> bool:
        if self.dat.start_new and self.no_longer_new():
            return False
        return self.new_start()

    def downstream_links(self) -> list[Handler]:
        for junc_unit in self.juncs:
            if self.junction_is_dns(junc_unit):
                return [junc_unit]
        return []

    def upstream_links(self) -> list[Handler]:
        for junc_unit in self.juncs:
            if not self.junction_is_dns(junc_unit):
                return [junc_unit]
        return []


class JunctionLinker(LinkHelper):

    def skip(self) -> bool:
        return True


class LateralLinker(JunctionLinker):

    def no_longer_new(self) -> bool:
        return False


class BoundaryLinker(LinkHelper):

    def new_start(self) -> bool:
        if not self.dat.start_new:
            return True
        return False

    def no_longer_new(self) -> bool:
        return False

    def junction_is_dns(self, junc: JunctionHandler) -> bool:
        if self.dat.start_new:
            return True
        return False

    def upstream_links(self) -> list[Handler]:
        ups_units = super().upstream_links()
        if ups_units:
            return ups_units
        if not self.unit.dns_units:
            for unit in self.dat.unit(self.unit.id, ()):
                if unit.uid != self.unit.uid:
                    return [unit]
            for unit in self.dat.units:
                if unit.TYPE == 'structure' and unit.dns_label.lower() == self.unit.id.lower():
                    return [unit]
        return []

    def downstream_links(self) -> list[Handler]:
        dns_units = super().downstream_links()
        if dns_units:
            return dns_units
        for unit in self.dat.unit(self.unit.id, ()):
            if unit.uid != self.unit.uid:
                if unit.TYPE == 'unit' and unit.dx > 0:
                    return [unit]
                elif unit.TYPE in ['structure', 'component'] and unit.ups_label.lower() == self.unit.id.lower():
                    return [unit]
                elif unit.type == 'LATERAL':
                    return [unit]
        return []


class QTLinker(BoundaryLinker):

    def junction_is_dns(self, junc: JunctionHandler) -> bool:
        return True  # assume QT boundaries connected to junctions are always going into the junction


class HydrologyLinker(QTLinker):
    pass


class StructureLinker(LinkHelper):

    def junction_is_dns(self, junc: JunctionHandler) -> bool:
        if self.unit.dns_label in junc.connections:
            return True
        return False

    def upstream_links(self) -> list[Handler]:
        ups_units = super().upstream_links()
        if ups_units:
            return ups_units
        for us_unit in self.dat.unit(self.unit.ups_label, ()):
            if not us_unit.dns_units and us_unit.uid != self.unit.uid:
                return [us_unit]
        return []

    def downstream_links(self) -> list[Handler]:
        dns_units = super().downstream_links()
        if dns_units:
            return dns_units
        for unit in self.dat.unit(self.unit.dns_label, ()):
            return [unit]
        for junc_unit in self.dat.find_units(self.dat._hnd_manager.handler_from_name('Junction')):
            if self.unit.dns_label in junc_unit.connections:
                return [junc_unit]
        for reservoir_unit in self.dat.find_units(self.dat._hnd_manager.handler_from_name('Reservoir')):
            if self.unit.dns_label in reservoir_unit.connections:
                return [reservoir_unit]
        # RIVER can also be downstream of spill units via the RIVER spill attributes,
        # this connection is handled by the RIVER unit
        return []


class ComponentLinker(StructureLinker):
    pass


class UnitLinker(LinkHelper):

    def junction_is_dns(self, junc: JunctionHandler) -> bool:
        if self.unit.dx == 0:
            return True
        return False

    def upstream_links(self) -> list[Handler]:
        ups_units = super().upstream_links()
        for lat_inflow in ['lat_inflow_1', 'lat_inflow_2', 'lat_inflow_3', 'lat_inflow_4']:
            if hasattr(self.unit, lat_inflow):
                lat_inflow_id = getattr(self.unit, lat_inflow)
                if lat_inflow_id:
                    lat_unit = self.dat.lat_from_lat_conn_id(lat_inflow_id)
                    if lat_unit:
                        ups_units.append(lat_unit)
        for lat_inflow_nd in ['lat_inflow_node_1', 'lat_inflow_node_2']:
            if hasattr(self.unit, lat_inflow_nd):
                lat_inflow_id = getattr(self.unit, lat_inflow_nd)
                if lat_inflow_id:
                    lat_unit = self.dat.lat_from_lat_conn_id_node(lat_inflow_id)
                    if lat_unit:
                        ups_units.append(lat_unit)
        for spill in ['spill_1', 'spill_2']:
            if hasattr(self.unit, spill):
                label = getattr(self.unit, spill)
                if label:
                    for spill_unit in self.dat.find_units(self.dat._hnd_manager.handler_from_name('Spill')):
                        if label.upper() == spill_unit.dns_label.upper():
                            ups_units.append(spill_unit)
        return ups_units

    def downstream_links(self) -> list[Handler]:
        dns_units = super().downstream_links()
        if self.unit.dx > 0:
            dns_idx = self.idx + 1
            if dns_idx < len(self.dat.units):
                dns_units.append(self.dat._units_order[dns_idx])
        for spill in ['spill_1', 'spill_2']:
            if hasattr(self.unit, spill):
                spill_unit_id = getattr(self.unit, spill)
                if spill_unit_id is not None:
                    spill_unit_uid = f'SPILL__{spill_unit_id}'
                    spill_unit = self.dat.unit(spill_unit_uid)
                    if spill_unit:
                        dns_units.append(spill_unit)
        return dns_units
