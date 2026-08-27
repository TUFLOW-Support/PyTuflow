from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .driver import DatabaseDriver
from ...tmf_types import PathLike


class TS1DatabaseDriver(DatabaseDriver):

    @staticmethod
    def test_is_ts1(path: PathLike) -> bool:
        return Path(path).suffix.lower() == '.ts1'

    def name(self) -> str:
        # docstring inherited
        return 'ts1'

    def load(self, path: PathLike, *args, **kwargs):
        # docstring inherited
        self.fpath = Path(path)
        with self.fpath.open() as f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    raise EOFError(f'End of TS1 file reached without finding any data: {self.fpath}')
                if line.strip().lower().startswith('time (min)'):
                    index = line.split(',')[0]
                    f.seek(pos)
                    df = pd.read_csv(f, index_col=index)
                    df.index.name = df.index.name.strip()
                    return df
