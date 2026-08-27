from .orifice import Orifice


class Outfall(Orifice):

    @staticmethod
    def unit_type_name() -> str:
        return 'OUTFALL'
