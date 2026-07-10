from ..._common.module import BaseEngineModule


class FVBaseModule(BaseEngineModule):
    """FV engine module base.  Sets ``ENGINE_TYPE = 'fv'`` so all config is
    loaded from the FV module cache directory."""

    ENGINE_TYPE: str = 'fv'
