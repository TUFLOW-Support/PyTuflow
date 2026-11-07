from pathlib import Path

from ..abc.tcf_base import TCFBase
from ..inp.cf import ControlFileInput
from ..parsers.command import Command
from .cf_build_state import ControlFileBuildState


class _OverrideInput(ControlFileInput):
    """Implicit include whose commands belong to a separate override file.

    Retaining a child control file gives context/dependency traversal the
    usual include semantics without inserting a synthetic command on write.
    """

    def write(self, fo, scope_writer):
        pass

    def _load_control_files(self):
        # An override is a continuation of this model, not a second TCF with
        # its own defaults, identity or implicit override discovery.
        self._cf_loaded_paths = []
        for file in self.files:
            self.cf.append(ControlFileBuildState(file, config=self.config, parent=self.parent))
            self._cf_loaded_paths.append(Path(file))


class TCFBuildState(ControlFileBuildState, TCFBase):
    def _load(self, path):
        super()._load(path)
        # _load also handles inline Read File inputs. Only the original TCF
        # gets an implicit override; the override itself must not discover one.
        if self.parent is not None or self._active_trd is not None:
            return
        override = self.config.tuflow_override(self.fpath)
        if override is not None:
            command = Command(f'Read File == {override.name}', self.config)
            self.inputs.append(_OverrideInput(self, command))
