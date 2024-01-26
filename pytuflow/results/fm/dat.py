import importlib
import re
from pathlib import Path
from typing import Union, TextIO

from .unpack_fixed_field import unpack_fixed_field


available_classes = {}
UNITS_DIR = Path(__file__).parent / 'units'
for fpath in UNITS_DIR.glob('*.py'):
    if fpath.stem.startswith('_'):
        continue
    class_pascal_case = ''.join([x[0].upper() + x[1:] for x in fpath.stem.lower().split('_')])
    module_ = getattr(importlib.import_module(f'pytuflow.results.fm.units.{fpath.stem.lower()}'), class_pascal_case)
    available_classes[fpath.stem.upper()] = module_


class Dat:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = Path(fpath)
        self.units = {}
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
                self.units[unit.id] = unit
                return
        self._finished = True
