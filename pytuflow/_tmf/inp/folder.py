from .file import FileInput
from .. import const


class FolderInput(FileInput):
    """Represents a folder input command.

    e.g. Log Folder == <>, or Output Folder == <>
    """
    TUFLOW_TYPE = const.INPUT.FOLDER

    def _load_files(self):
        super()._load_files()
        self._files = []
        self._files_loaded = True
