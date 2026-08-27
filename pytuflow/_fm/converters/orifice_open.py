from .orifice import Orifice


class OrificeOpen(Orifice):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'ORIFICE_OPEN'
