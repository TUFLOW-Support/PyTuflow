from pathlib import Path

from .cf import ControlFile
from ..cf.cf_run_state import ControlFileRunState
from ..settings import TCFConfig, _ParseContext
from ..event import EventDatabase
from ..parsers.non_recursive_basic_parser import get_event_commands


class TEFBase(ControlFile):

    @staticmethod
    def parse_event_file(fpath: str | Path, config: TCFConfig | _ParseContext | None = None, parent: 'ControlFile' = None) -> EventDatabase:
        """Static method to parse the event file and return an EventDatabase.

        Parameters
        ----------
        fpath : str | Path
            The path to the event file (``.tef``)
        config : TCFConfig, optional
            The configuration settings for the TCF.
        parent : ControlFile, optional
            The parent control file.

        Returns
        -------
        EventDatabase
            An instance of EventDatabase containing parsed events.

        Examples
        --------
        >>> from pytuflow import TEF
        >>> TEF.parse_event_file('path/to/event_file.tef')
        {'Q100': {'_event_': '100yr2hr'}, 'QPMF': {'_event_': 'PMFyr2hr'}}
        """
        from ..inp.event import EventInput
        config = TCFConfig() if config is None else config
        event_db = EventDatabase()
        for event_command in get_event_commands(Path(fpath), config):
            if event_command.is_event_source():
                parent_ = parent.bs if isinstance(parent, ControlFileRunState) else parent
                inp = EventInput(parent_, event_command)
                if inp.event_name:
                    event_db[inp.event_name] = {inp.event_var: inp.event_value}
                event_db.inputs.append(inp)
            elif event_command.is_start_define():
                event_db[event_command.value] = {}
        return event_db

    def event_database(self) -> EventDatabase:
        """Returns the EventDatabase for this TEF instance.

        Returns
        -------
        EventDatabase
            An instance of EventDatabase containing parsed events from the TEF file.

        Examples
        --------
        >>> tcf = ... # Assume this is an instance of TCF
        >>> tcf.tef().event_database()
        {'Q100': {'_event_': '100yr2hr'}, 'QPMF': {'_event_': 'PMFyr2hr'}}
        """
        if not self._fpath:
            raise ValueError("TEF file path is not set.")
        return self.parse_event_file(self._fpath, self.config)
