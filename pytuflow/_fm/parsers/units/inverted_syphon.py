from .orifice import Orifice


class InvertedSyphon(Orifice):

    @staticmethod
    def unit_type_name() -> str:
        return 'INVERTED SYPHON'
