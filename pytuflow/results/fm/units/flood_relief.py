from .orifice import Orifice

SUB_UNIT_NAME = 'FLOOD RELIEF'


class FloodRelief(Orifice):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME

    def __repr__(self) -> str:
        return f'<{SUB_UNIT_NAME} {self.sub_name} {self.id}>'


AVAILABLE_CLASSES = [FloodRelief]
