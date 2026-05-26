import logging
import re

from .mat_db_entry import MatDBEntry
from ..scope import Scope, ScopeList
from ..abc.run_state import RunState



logger = logging.getLogger('pytuflow')


class BCDatabaseEntry(MatDBEntry):

    def _load_files(self):
        super()._load_files()
        if not self.uses_source_file:
            return
        if isinstance(self.parent, RunState):
            return

        if self._has_missing_files:  # reset this and check for files using event combinations
            self._has_missing_files = False
            self._files.clear()

        source_part = [x for x in self.line.parts()][self.SOURCE_INDEX]
        seen = set(self._files)

        for comb in self.config.event_db.event_combinations():
            file = str(source_part.value)
            scope_list = ScopeList()
            for event in comb:
                event_var, event_val = event
                if event_var.lower() in file.lower():
                # if re.findall(re.escape(event_var), file, flags=re.IGNORECASE):
                    scope = Scope('Event Define', event_val, event_var)
                    if scope not in scope_list:
                        scope_list.append(scope)
                    file = re.sub(re.escape(event_var), str(event_val), file, flags=re.IGNORECASE)

            if '<<' in file:
                continue

            file = self.parent.fpath.parent / file

            if file not in seen:
                seen.add(file)
                self._files.append(file)
                self._file_to_scope[str(file)] = scope_list

        self._check_missing_files(source_part)
