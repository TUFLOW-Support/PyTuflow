from contextlib import contextmanager


class GPKGBase:

    @contextmanager
    def _connect(self):
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(self.fpath)
            yield conn
        finally:
            if conn is not None:
                conn.close()
