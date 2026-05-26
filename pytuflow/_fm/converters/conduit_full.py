from .conduit_full_arch import ConduitFullArch


class ConduitFull(ConduitFullArch):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_FULL'
