from .orifice import Orifice


SUB_UNIT_NAME = 'INVERTED SYPHON'


class InvertedSyphon(Orifice):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME

    def __repr__(self) -> str:
        return f'<{SUB_UNIT_NAME} {self.sub_name} {self.id}>'


AVAILABLE_CLASSES = [InvertedSyphon]
