import re
import struct
from datetime import datetime
import numpy as np
from pathlib import Path

from pytuflow.types import PathLike


pNNODES = 129
pDT = 256
pTIMESTEP_FIRST = 260
pTIMESTEP_LAST = 384
pOUT_INTERVAL = 388
pLABEL_LEN = 396
pDATE = 400
pFIRST_LABEL = 640


def byte2str(b: bytes) -> str:
    """Convert bytes to string.

    Parameters
    ----------
    b: bytes
        Bytes to convert.

    Returns
    -------
    str
        Converted string.
    """
    return re.sub(rf'[{chr(0)}-{chr(31)}]', '', b''.join(b).decode('utf-8', errors='ignore')).strip()


class ZZL:
    """Class for reading ZZL files."""

    def __init__(self, zzl_path: PathLike) -> None:
        """
        Parameters
        ----------
        zzl_path: PathLike
            Path to the ZZL file.
        """
        #: list[str]: Node labels.
        self.labels = []
        #: int: Number of result types.
        self.nvars = 6
        with zzl_path.open('rb') as f:
            self._model_title = byte2str(struct.unpack('c'*128, f.read(128)))
            #: str: Model name
            self.model_title = self._model_title.split('FILE=')[0].strip()
            #: str: DAT file name.
            self.dat = self._model_title.split('FILE=')[1].split('.dat')[0].strip() + '.dat'
            #: str: Flood Modeller version.
            self.fm_version = self._model_title.split('VER=')[1].strip()
            #: int: Number of nodes.
            self.nnodes = struct.unpack('I', f.read(4))[0]
            f.seek(pDT)
            #: float: Timestep.
            self.dt = struct.unpack('f', f.read(4))[0]
            f.seek(pTIMESTEP_FIRST)
            #: float: First timestep.
            self.timestep_first = struct.unpack('I', f.read(4))[0]
            f.seek(pTIMESTEP_LAST)
            #: float: Last timestep.
            self.timestep_last = struct.unpack('I', f.read(4))[0]
            f.seek(pOUT_INTERVAL)
            #: float: Output interval.
            self.output_interval = float(struct.unpack('I', f.read(4))[0])
            f.seek(pLABEL_LEN)
            #: int: Character length of node labels
            self.label_len = struct.unpack('I', f.read(4))[0]
            f.seek(pDATE)
            hr = struct.unpack('I', f.read(4))[0]
            min = struct.unpack('I', f.read(4))[0]
            day = struct.unpack('I', f.read(4))[0]
            mon = struct.unpack('I', f.read(4))[0]
            yr = struct.unpack('I', f.read(4))[0]
            #: datetime: Reference time.
            self.reference_time = datetime(yr, mon, day, hr, min)
            f.seek(pFIRST_LABEL)
            for i in range(self.nnodes):
                if i != 0 and i % 10 == 0:
                    f.read(8)
                self.labels.append(byte2str(struct.unpack('c'*self.label_len, f.read(self.label_len))))


class ZZN:
    """Class for reading Flood Modeller ZZN files."""

    def __init__(self, file_path: PathLike) -> None:
        """
        Parameters
        ----------
        file_path: PathLike
            Path to the ZZN file.
        """
        self._zzn_path = Path(file_path)
        self._zzl_path = self._zzn_path.with_suffix('.zzl')
        if not self._zzl_path.exists():
            raise FileNotFoundError(f'zzl file not found: {self._zzl_path}')
        self._zzl = ZZL(self._zzl_path)
        self._a = np.fromfile(str(self._zzn_path), dtype=np.float32, count=self.timestep_count()*self.node_count()*self.result_type_count())
        self._a = np.reshape(self._a, (self.timestep_count(), self.node_count()*self.result_type_count()))
        self._h = np.array(sum([['Flow', 'Stage', 'Froude', 'Velocity', 'Mode', 'State'] for _ in range(self.node_count())], []))

    def get_time_series_data(self, typ: str) -> np.ndarray:
        """Time series data for a given result type.

        Parameters
        ----------
        typ: str
            Result type. One of 'Flow', 'Stage', 'Froude', 'Velocity', 'Mode', 'State'.

        Returns
        -------
        np.ndarray
            Time series data.
        """
        return self._a[:,self._h == typ]

    def labels(self) -> list[str]:
        """Return node labels.

        Returns
        -------
        list[str]
            Node labels.
        """
        return self._zzl.labels[:]

    def output_interval(self) -> float:
        """Return output interval.

        Returns
        -------
        float
            Output interval.
        """
        return self._zzl.output_interval

    def node_count(self) -> int:
        """Returns node count.

        Returns
        -------
        int
            Node count.
        """
        return self._zzl.nnodes

    def floodmodeller_version(self) -> str:
        """Return Flood Modeller version.

        Returns
        -------
        str
            Flood Modeller version.
        """
        return self._zzl.fm_version

    def result_name(self) -> str:
        """Return result name.

        Returns
        -------
        str
            Result name.
        """
        return self._zzl.model_title

    def first_timestep(self) -> float:
        """Return first timestep.

        Returns
        -------
        float
            First timestep.
        """
        return self._zzl.timestep_first

    def last_timestep(self) -> float:
        """Return last timestep.

        Returns
        -------
        float
            Last timestep.
        """
        return self._zzl.timestep_last

    def timestep_count(self) -> int:
        """Return timestep count.

        Returns
        -------
        int
            Timestep count.
        """
        return int((self._zzl.timestep_last - self._zzl.timestep_first) / self._zzl.output_interval) + 1

    def result_type_count(self) -> int:
        """Return result type count.

        Returns
        -------
        int
            Result type count.
        """
        return self._zzl.nvars

    def reference_time(self) -> datetime:
        """Return reference time.

        Returns
        -------
        datetime
            Reference time.
        """
        return self._zzl.reference_time
