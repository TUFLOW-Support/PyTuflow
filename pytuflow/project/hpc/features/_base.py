from __future__ import annotations

# Re-export utilities that tests and other modules import from this location.
from ..._common.utils import _normalize_slashes, _parse_filter  # noqa: F401
from ..._common.feature import BaseEngineFeature


class HPCBaseFeature(BaseEngineFeature):
    """HPC engine feature base.  Thin subclass of :class:`BaseEngineFeature` that
    sets ``ENGINE_TYPE = 'hpc'`` so all config is loaded from the HPC feature
    cache directory.
    """

    ENGINE_TYPE: str = 'hpc'
