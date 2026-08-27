from .orifice import Orifice


class InvertedSyphonOpen(Orifice):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'INVERTED SYPHON_OPEN'
