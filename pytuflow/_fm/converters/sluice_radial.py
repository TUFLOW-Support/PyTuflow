from .sluice_vertical import SluiceVertical


class SluiceRadial(SluiceVertical):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'SLUICE_RADIAL'
