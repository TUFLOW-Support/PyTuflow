import typing

from . import DatasetEngine


class TwoDMEngine(DatasetEngine):
    ENGINE_NAME = '2dm'

    @staticmethod
    def available() -> bool:
        return True

    def iterate(self, data_path: str = '') -> typing.Generator[str, None, None]:
        return []

    def is_xmdf(self) -> bool:
        return False

    def get_property(self, data_path: str, property_name: str) -> typing.Any:
        return ''
