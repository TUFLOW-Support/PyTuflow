class GPKGBase:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fpath = None
        self._db = None
        self._cur = None
        self._keep_open = 0

    def _open_db(self) -> None:
        import sqlite3
        if self._db is None:
            self._db = sqlite3.connect(self.fpath)
            self._cur = self._db.cursor()
        else:
            self._keep_open += 1

    def _close_db(self) -> None:
        if self._db is not None:
            if not self._keep_open:
                self._cur = None
                self._db.close()
                self._db = None
            else:
                self._keep_open -= 1