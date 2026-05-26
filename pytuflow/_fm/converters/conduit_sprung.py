from .conduit_sprung_arch import ConduitSprungArch


class ConduitSprung(ConduitSprungArch):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_SPRUNG'
