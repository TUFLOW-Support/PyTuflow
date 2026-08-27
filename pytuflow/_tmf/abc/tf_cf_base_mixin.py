import typing


if typing.TYPE_CHECKING:
    from .tcf_base import TCFBase


class TuflowControlFileMixin:
    """TUFLOW HPC/Classic control file specific mixins."""

    @property
    def tcf(self) -> 'TCFBase':
        return self.root_cf
