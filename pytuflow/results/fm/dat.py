import importlib
import re
from pathlib import Path
from typing import Union, TextIO
from ..types import PathLike

from .unpack_fixed_field import unpack_fixed_field
from .units._unit import Unit


available_classes = {}
available_units = []
UNITS_DIR = Path(__file__).parent / 'units'
for fpath in UNITS_DIR.glob('*.py'):
    if fpath.stem.startswith('_'):
        continue
    class_pascal_case = ''.join([x[0].upper() + x[1:] for x in fpath.stem.lower().split('_')])
    mod = importlib.import_module(f'pytuflow.results.fm.units.{fpath.stem.lower()}')
    cls = getattr(mod, class_pascal_case)
    sub_unit_name = getattr(mod, 'SUB_UNIT_NAME')
    available_classes[fpath.stem.upper()] = cls
    if sub_unit_name:
        available_units.append(f'{fpath.stem.upper()}_{sub_unit_name}')
    else:
        available_units.append(fpath.stem.upper())


class Dat:

    def __init__(self, fpath: PathLike) -> None:
        self.fpath = Path(fpath)
        self._units_id = {}
        self._units_uid = {}
        self._fixed_field_length = self.fixed_field_length()
        self._started = False
        self._finished = False
        self._load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<DAT {self.fpath.stem}>'
        return '<DAT>'

    def fixed_field_length(self) -> int:
        fixed_field_length = 12  # default to latest
        try:
            with self.fpath.open() as fo:
                for line in fo:
                    if '#REVISION#' in line:
                        line = fo.readline()
                        header = unpack_fixed_field(line, [10] * 7)
                        if len(header) >= 6:
                            fixed_field_length = int(header[5])
                        break
        except IOError:
            pass
        except ValueError:
            pass
        except Exception:
            pass

        return fixed_field_length

    def unit(self, id_: str) -> Union[None, 'Unit']:
        if id_ in self._units_id:
            return self._units_id[id_]
        if id_ in self._units_uid:
            return self._units_uid[id_]

    def _load(self) -> None:
        with self.fpath.open() as f:
            while not self._started:
                self._load_header(f)
            while not self._finished:
                self._load_unit(f)

    def _load_header(self, fo: TextIO) -> None:
        for line in fo:
            if line.startswith('END GENERAL'):
                self._started = True
            return
        self._finished = True

    def _load_unit(self, fo: TextIO) -> None:
        for line in fo:
            if re.findall(r'^(GISINFO|INITIAL CONDITIONS)', line):
                break
            unit = None
            for unit_type, unit_class in available_classes.items():
                if line.startswith(unit_type):
                    unit = unit_class(fo, self._fixed_field_length)
                    break
            if unit is not None:
                self._units_id[unit._id] = unit
                self._units_uid[unit.id] = unit
                return
        self._finished = True
