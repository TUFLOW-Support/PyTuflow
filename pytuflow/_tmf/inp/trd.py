from .cf import FileInput
from .. import const


class TuflowReadFileInput(FileInput):
    TUFLOW_TYPE = const.INPUT.TRD

    def _load_files(self):
        super()._load_files()
        self._files_loaded = True
