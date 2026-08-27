from .orifice import Orifice


class OutfallFlapped(Orifice):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'OUTFALL_FLAPPED'
