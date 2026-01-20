import typing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import struct
from collections import OrderedDict

import numpy as np

from . import PyDataExtractor


class Card:
    ID: int = -1
    SIZE: int = 0
    DTYPE: str = ''
    NFIELD: int = 0
    SFLG_2_DECODE = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}
    SFLT_2_DECODE = {4: 'f', 8: 'd'}

    def __init__(self, *args, **kwargs):
        self.ret = ()

    def __repr__(self):
        return f'<{self.__class__.__name__} ID={self.ID} VARIABLE={self.VARIABLE} ret={self.ret}>'

    def read(self, buf: bytes) -> int:
        if self.SIZE * self.NFIELD == 0:
            return 0
        self.ret = struct.unpack(self.DTYPE * self.NFIELD, buf[:self.SIZE * self.NFIELD])
        return self.SIZE * self.NFIELD


class Version(Card):
    VARIABLE = 'Version'
    ID = 3000
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 0


class ObjType(Card):
    VARIABLE = 'type'
    ID = 100
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class SFLT(Card):
    VARIABLE = 'sizefloat'
    ID = 110
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class SFLG(Card):
    VARIABLE = 'sizeflag'
    ID = 120
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class BegScl(Card):
    VARIABLE = 'beginscalar'
    ID = 130
    SIZE = 0
    DTYPE = 'i'
    NFIELD = 0


class BegVec(Card):
    VARIABLE = 'beginvector'
    ID = 140
    SIZE = 0
    DTYPE = 'i'
    NFIELD = 0


class VecType(Card):
    VARIABLE = 'vectortype'
    ID = 150
    SIZE = 8
    DTYPE = 'i'
    NFIELD = 1


class ObjID(Card):
    VARIABLE = 'id'
    ID = 160
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class NumData(Card):
    VARIABLE = 'numdata'
    ID = 170
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class NumCells(Card):
    VARIABLE = 'numcells'
    ID = 180
    SIZE = 4
    DTYPE = 'i'
    NFIELD = 1


class Name(Card):
    VARIABLE = 'name'
    ID = 190
    SIZE = 1
    DTYPE = 'c'
    NFIELD = 100

    def read(self, buf: bytes) -> int:
        size = 40
        for size_ in [40, 80]:
            v = struct.unpack('i', buf[size_:size_+4])[0]
            if v == 200:
                size = size_
                break
        vals = struct.unpack(self.DTYPE * size, buf[:size])
        self.ret = b''.join(vals).decode('utf-8').strip('\x00').strip()
        return size


class TS(Card):
    VARIABLE = 'timestep'
    ID = 200
    SIZE = 4
    DTYPE = 'f'
    NFIELD = 1

    def __init__(self, sflg: int, sflt: int, numdata: int, numcells: int, is_vector: bool):
        super().__init__()
        self.sflg = sflg
        self.sflt = sflt
        self.i = self.SFLG_2_DECODE.get(sflg, 'i')
        self.f = self.SFLT_2_DECODE.get(sflt, 'f')
        self.numdata = numdata
        self.numcells = numcells
        self.is_vector = is_vector
        self.times = np.ndarray([])
        self.stat = np.ndarray([])
        self.val = np.ndarray([])
        self._stat = []
        self._val = []
        self._times = []

    def read(self, buf: bytes) -> int:
        first = True
        istat = struct.unpack(self.i, buf[:self.sflg])[0]
        stat = np.full((self.numdata,), 1 if istat == 1 else 0, dtype='i4').tolist()
        k = self.sflg
        counter_limit = 10_000
        counter = 0
        while struct.unpack('i', buf[k:k+4])[0] != 210 or counter > counter_limit:
            if not first:
                k += 4  # skip TS id
                istat = struct.unpack(self.i, buf[k:k + self.sflg])[0]
                k += self.sflg
            time = struct.unpack(self.f, buf[k:k + self.sflt])[0]
            k += self.sflt
            self._times.append(time)
            if istat == 0:
                stat = stat[:]
            else:
                stat = struct.unpack(self.i * self.numcells, buf[k:k + self.sflg * self.numcells])
                k += self.sflg * self.numcells
            self._stat.append(stat)
            if self.is_vector:
                val = struct.unpack(self.f * self.numdata * 2, buf[k:k + self.sflt * self.numdata * 2])
            else:
                val = struct.unpack(self.f * self.numdata, buf[k:k + self.sflt * self.numdata])
            self._val.append(val)
            k += self.sflt * self.numdata * (2 if self.is_vector else 1)
            first = False
            counter += 1

        if counter >= counter_limit:
            raise RuntimeError('Exceeded maximum number of timesteps while reading TS card; possible malformed file.')

        shape = (len(self._times), self.numdata) if not self.is_vector else (len(self._times), self.numdata, 2)
        self.val = np.array(self._val, dtype=self.f).reshape(shape)
        self.stat = np.array(self._stat, dtype=bool).reshape((len(self._times), self.numcells))
        self.times = np.array(self._times, dtype=self.f)
        return k


class ENDDS(Card):
    VARIABLE = 'enddataset'
    ID = 210
    SIZE = 0
    DTYPE = 'i'
    NFIELD = 0


class RT_JULIAN(Card):
    VARIABLE = 'reference_time'
    ID = 240
    SIZE = 8
    DTYPE = 'd'
    NFIELD = 1


class TimeUnits(Card):
    VARIABLE = 'time_units'
    ID = 250
    SIZE = 4
    DTYPE = 'f'
    NFIELD = 1


_CARDS = [Version, ObjType, SFLT, SFLG, BegScl, BegVec, VecType, ObjID, NumData, NumCells, Name, TS, ENDDS, RT_JULIAN,
          TimeUnits]
CARDS = {x.ID: x for x in _CARDS}



class PyDATDataExtractor(PyDataExtractor):

    def __init__(self, fpaths: list[str | Path]):
        super().__init__()
        self._dats = [Path(f) for f in fpaths]
        self._results = OrderedDict()
        for f in self._dats:
            dtype = self.translate_file_name(f)
            self._results[dtype] = self.extract_results_from_file(f)

    def times(self, data_type: str) -> np.ndarray:
        dtype, is_max, is_min = self.strip_data_type(data_type)
        if is_max or is_min:
            return np.ndarray([])
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        time_conv = 1.
        time_units_card = cards.get('time_units')
        if time_units_card:
            d = {0.: 1., 1.: 60., 2.: 3600}
            time_conv = d.get(time_units_card.ret[0], 1.)
        ts_card = cards.get('timestep')
        if ts_card:
            return ts_card.times[(ts_card.times < 99998) & (ts_card.times > -99998)] * time_conv
        return np.ndarray([])

    def data_types(self) -> list[str]:
        # yield maximums first
        data_types = []
        for dtype, cards in self._results.items():
            ts_card = cards.get('timestep')
            if not ts_card:
                continue
            if np.any(ts_card.times == 99999.):
                data_types.append(f'{dtype}/Maximums')
        # yield minimums
        for dtype, cards in self._results.items():
            ts_card = cards.get('timestep')
            if not ts_card:
                continue
            if np.any(ts_card.times == -99999.):
                data_types.append(f'{dtype}/Minimums')
        # yield regular data types
        data_types.extend(list(self._results.keys()))
        return data_types

    def reference_time(self, data_type: str) -> datetime | None:
        dtype, _, _ = self.strip_data_type(data_type)
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        rt_card = cards.get('reference_time')
        if not rt_card:
            return None

        jd = rt_card.ret[0]
        if jd <= 0:
            return None

        unix_epoch_jd = 2440587.5
        seconds_per_day = 86400

        seconds = (jd - unix_epoch_jd) * seconds_per_day
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)

    def is_vector(self, data_type: str) -> bool:
        dtype, _, _ = self.strip_data_type(data_type)
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        beg_vec_card = cards.get('timestep')
        if not beg_vec_card:
            return False
        return beg_vec_card.is_vector

    def is_static(self, data_type: str) -> bool:
        dtype, is_max, is_min = self.strip_data_type(data_type)
        if is_max or is_min:
            return True
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        ts_card = cards.get('timestep')
        if not ts_card:
            return True
        return ts_card.times.size < 2

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        data = self._data(data_type)
        return data[index]

    def wd_flag(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        stat = self._stat(data_type)
        return stat[index]

    def _data(self, data_type: str) -> np.ndarray:
        dtype, is_max, is_min = self.strip_data_type(data_type)
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        ts_card = cards.get('timestep')
        if not ts_card:
            return np.ndarray([])
        if is_min:
            idx = np.flatnonzero(ts_card.times == -99999.)
            if idx.size == 0:
                raise ValueError(f'Data type {data_type} not found.')
            data = ts_card.val[idx[0], ...]
        elif is_max:
            idx = np.flatnonzero(ts_card.times == 99999.)
            if idx.size == 0:
                raise ValueError(f'Data type {data_type} not found.')
            data = ts_card.val[idx[0], ...]
        else:
            idx = np.flatnonzero((ts_card.times < 99998.) & (ts_card.times > -99998.))
            data = ts_card.val[idx, ...]
        return data

    def _stat(self, data_type: str) -> np.ndarray:
        dtype, is_max, is_min = self.strip_data_type(data_type)
        cards = self._results.get(dtype, {})
        if not cards:
            raise ValueError(f'Data type {data_type} not found.')
        ts_card = cards.get('timestep')
        if not ts_card:
            return np.ndarray([])
        if is_min:
            idx = np.flatnonzero(ts_card.times == -99999.)
            if idx.size == 0:
                raise ValueError(f'Data type {data_type} not found.')
            stat = ts_card.stat[idx[0], ...]
        elif is_max:
            idx = np.flatnonzero(ts_card.times == 99999.)
            if idx.size == 0:
                raise ValueError(f'Data type {data_type} not found.')
            stat = ts_card.stat[idx[0], ...]
        else:
            idx = np.flatnonzero((ts_card.times < 99998.) & (ts_card.times > -99998.))
            stat = ts_card.stat[idx, ...]
        return stat

    @staticmethod
    def translate_file_name(filename: Path) -> str:
        """Translates the file name to data type name."""
        from ...map_output import MapOutput
        name = filename.stem
        dtype = name.rsplit('_', 1)[1]
        return MapOutput._get_standard_data_type_name(dtype)

    @staticmethod
    def extract_results_from_file(fpath: Path) -> dict[str, Card]:
        with fpath.open('rb') as fo:
            buf = fo.read()
        k = 0
        cards = {}
        sflg = 4
        sflt = 4
        numdata = 0
        numcells = 0
        is_vector = False
        while k < len(buf):
            card_id = struct.unpack('i', buf[k:k+4])[0]
            card_cls = CARDS.get(card_id, None)
            if card_cls is None:
                raise ValueError(f'Unknown card ID {card_id} at position {k} in file {fpath}')
            card = card_cls(sflg, sflt, numdata, numcells, is_vector)
            size = card.read(buf[k+4:])
            cards[card.VARIABLE] = card
            k += 4 + size

            if card.VARIABLE == 'sizeflag':
                sflg = card.ret[0]
            elif card.VARIABLE == 'sizefloat':
                sflt = card.ret[0]
            elif card.VARIABLE == 'numdata':
                numdata = card.ret[0]
            elif card.VARIABLE == 'numcells':
                numcells = card.ret[0]
            elif card.VARIABLE == 'beginscalar':
                is_vector = False
            elif card.VARIABLE == 'beginvector':
                is_vector = True

        return cards

    @staticmethod
    def strip_data_type(data_type: str) -> tuple[str, bool, bool]:
        is_max, is_min = False, False
        ret = data_type
        if data_type.lower().endswith('/maximums') or data_type.startswith('max '):
            is_max = True
            if data_type.lower().endswith('/maximums'):
                ret = data_type[:-9].strip()
            else:
                ret = data_type[4:].strip()
        elif data_type.lower().endswith('/minimums') or data_type.startswith('min '):
            is_min = True
            if data_type.lower().endswith('/minimums'):
                ret = data_type[:-9].strip()
            else:
                ret = data_type[4:].strip()
        return ret, is_max, is_min
