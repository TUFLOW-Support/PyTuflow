from .orifice import Orifice


class OrificeFlapped(Orifice):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'ORIFICE_FLAPPED'
