from .orifice import Orifice


class FloodReliefArchFlapped(Orifice):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'FLOOD RELIEF_FLAPPED'
