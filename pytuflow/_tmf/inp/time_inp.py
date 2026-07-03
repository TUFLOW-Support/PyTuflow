import datetime
import logging

from .. import const
from ..parsers.command import Command
from ..inp.setting import SettingInput


logger = logging.getLogger('pytuflow')


class TimeInputMixin:

    def _parse_time(self, command: Command):
        if command.config.time_format == 'HOURS':
            try:
                return float(command.value)
            except ValueError:
                return command.value
        elif command.config.time_format == 'ISODATE':
            try:
                if command.config.ISODATE_FORMAT:
                    return datetime.datetime.strptime(command.value, command.config.ISODATE_FORMAT)
                else:
                    return datetime.datetime.fromisoformat(command.value)
            except ValueError:
                logger.warning(f"Failed to parse time value '{command.value}' as ISODATE. Returning raw string.")
                return command.value
        else:
            return command.value
            

class TimeInput(SettingInput, TimeInputMixin):
    TUFLOW_TYPE = const.INPUT.TIME
    
    @property
    def value(self) -> str | float | datetime.datetime | None:
        return self._parse_time(self._command)
