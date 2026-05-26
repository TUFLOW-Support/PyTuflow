import typing


class ControlBase:
    pass


T_ControlFile = typing.TypeVar('T_ControlFile', bound='ControlBase')
