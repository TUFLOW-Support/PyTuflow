import re
import struct
from datetime import datetime
import numpy as np
from pathlib import Path

from .._pytuflow_types import PathLike


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

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath: PathLike
            Path to the ZZL file.
        """
        #: Path: Path to the ZZL file.
        self.fpath = Path(fpath)
        #: list[str]: Node labels.
        self.labels = []
        #: int: Number of result types.
        self.nvars = 6
        with self.fpath.open('rb') as f:
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
            #: int: Save multiple
            self.save_multiple = struct.unpack('I', f.read(4))[0]
            #: float: Output interval.
            self.output_interval = float(self.save_multiple) * self.dt
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

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath: PathLike
            Path to the ZZN file.
        """
        #: Path: Path to the ZZN file.
        self.fpath = Path(fpath)
        self._zzn_path = Path(fpath)
        self._zzl_path = self._zzn_path.with_suffix('.zzl')
        if not self._zzl_path.exists():
            raise FileNotFoundError(f'zzl file not found: {self._zzl_path}')
        #: ZZL: Associated ZZL object.
        self.zzl = ZZL(self._zzl_path)
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
        return self.zzl.labels[:]

    def output_interval(self) -> float:
        """Return output interval.

        Returns
        -------
        float
            Output interval.
        """
        return self.zzl.output_interval

    def node_count(self) -> int:
        """Returns node count.

        Returns
        -------
        int
            Node count.
        """
        return self.zzl.nnodes

    def floodmodeller_version(self) -> str:
        """Return Flood Modeller version.

        Returns
        -------
        str
            Flood Modeller version.
        """
        return self.zzl.fm_version

    def result_name(self) -> str:
        """Return result name.

        Returns
        -------
        str
            Result name.
        """
        return self.zzl.model_title

    def first_timestep(self) -> float:
        """Return first timestep.

        Returns
        -------
        float
            First timestep.
        """
        return self.zzl.timestep_first

    def last_timestep(self) -> float:
        """Return last timestep.

        Returns
        -------
        float
            Last timestep.
        """
        return self.zzl.timestep_last

    def timestep_count(self) -> int:
        """Return timestep count.

        Returns
        -------
        int
            Timestep count.
        """
        model_duration = (self.zzl.timestep_last - self.zzl.timestep_first + 1) * self.zzl.dt  # in seconds
        return int(np.round(model_duration / self.zzl.output_interval)) + 1

    def timesteps(self):
        """Return the timesteps.

        Returns
        -------
        list[float]
            Timesteps.
        """
        start_time = (self.zzl.timestep_first - 1) * self.zzl.dt / 3600
        end_time = self.zzl.timestep_last * self.zzl.dt / 3600
        a = np.arange(start_time, end_time, self.zzl.output_interval / 3600)
        if not np.isclose(a[-1], end_time, rtol=0., atol=0.001):
            a = np.append(a, np.reshape(end_time, (1,)), axis=0)
        return a.tolist()

    def result_type_count(self) -> int:
        """Return result type count.

        Returns
        -------
        int
            Result type count.
        """
        return self.zzl.nvars

    def reference_time(self) -> datetime:
        """Return reference time.

        Returns
        -------
        datetime
            Reference time.
        """
        return self.zzl.reference_time
