from ..._common.feature import BaseEngineFeature


class FVBaseFeature(BaseEngineFeature):
    """FV engine feature base.  Sets ``ENGINE_TYPE = 'fv'`` so all config is
    loaded from the FV feature cache directory."""

    ENGINE_TYPE: str = 'fv'
