from .orifice import Orifice


class FloodRelief(Orifice):

    @staticmethod
    def unit_type_name() -> str:
        return 'FLOOD RELIEF'
