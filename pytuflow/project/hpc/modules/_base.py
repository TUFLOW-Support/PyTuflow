from __future__ import annotations

# Re-export utilities that tests and other modules import from this location.
from ..._common.utils import _normalize_slashes, _parse_filter  # noqa: F401
from ..._common.module import BaseEngineModule


class HPCBaseModule(BaseEngineModule):
    """HPC engine module base.  Thin subclass of :class:`BaseEngineModule` that
    sets ``ENGINE_TYPE = 'hpc'`` so all config is loaded from the HPC module
    cache directory.
    """

    ENGINE_TYPE: str = 'hpc'
