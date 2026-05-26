import typing

from .inp_build_state import InputBuildState
from .. import const


class SettingInput(InputBuildState):
    """
    Input for Settings or Set commands.

    e.g.

    | :code:`TUTORIAL Model == ON`
    | :code:`Set Code == 0`
    """
    TUFLOW_TYPE = const.INPUT.SETTING

    @property
    def value(self) -> str | float | int | tuple[str | float | int, ...]:
        # docstring inherited
        self._command.reload_value()
        if self._command.is_value_a_number_3():  # e.g. Set Code == 0
            return self._command.return_number()
        elif self._command.is_value_a_number_tuple():  # e.g. Set Grid Siz (X,Y) == 800, 1000
            return self._command.return_number_tuple()
        return str(self._command.value) if self._command.value else ''

    @value.setter
    def value(self, value: typing.Any):
        raise AttributeError('The "value" attribute is read-only, use "rhs" to set the value of the input.')
