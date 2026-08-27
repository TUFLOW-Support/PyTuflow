from .link_helper import *


class Linker:

    def __init__(self, unit: Handler) -> None:
        self.unit = unit
        self.link_helper = None
        if self.unit.TYPE == 'junction':
            self.link_helper = JunctionLinker(self.unit)
        elif self.unit.type == 'LATERAL':
            self.link_helper = LateralLinker(self.unit)
        elif self.unit.TYPE in ['boundary', 'hydrology']:
            if self.unit.type == 'QTBDY':
                self.link_helper = QTLinker(self.unit)
            elif self.unit.TYPE == 'hydrology':
                self.link_helper = HydrologyLinker(self.unit)
            else:
                self.link_helper = BoundaryLinker(self.unit)
        elif self.unit.TYPE == 'component':
            self.link_helper = ComponentLinker(self.unit)
        elif self.unit.TYPE == 'structure':
            self.link_helper = StructureLinker(self.unit)
        elif self.unit.TYPE == 'unit':
            self.link_helper = UnitLinker(self.unit)
        else:
            self.link_helper = LinkHelper(self.unit)

    def skip(self) -> bool:
        return self.link_helper.skip()

    def downstream_links(self) -> list[Handler]:
        return self.link_helper.downstream_links()

    def upstream_links(self) -> list[Handler]:
        return self.link_helper.upstream_links()

    def start_new(self) -> bool:
        return self.link_helper.start_new()
