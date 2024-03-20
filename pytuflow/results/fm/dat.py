import importlib
import json
import re
from pathlib import Path
from typing import Union, TextIO
from ..types import PathLike

from .unpack_fixed_field import unpack_fixed_field
from .units._unit import Unit

from ...tmf.tmf.tuflow_model_files.db.drivers.dat import Dat as Dat_, Link


UNITS_DIR = Path(__file__).parent / 'units'
available_classes = []
available_units = []


def get_available_classes():
    for fpath in UNITS_DIR.glob('*.py'):
        if fpath.stem.startswith('_'):
            continue
        mod = importlib.import_module(f'pytuflow.results.fm.units.{fpath.stem.lower()}')
        sub_unit_name = getattr(mod, 'SUB_UNIT_NAME')
        clss = getattr(mod, 'AVAILABLE_CLASSES')
        for i, cls in enumerate(clss):
            available_classes.append(cls)
            if i == 0:
                available_units.append(sub_unit_name)

        # class_pascal_case = ''.join([x[0].upper() + x[1:] for x in fpath.stem.lower().split('_')])
        # mod = importlib.import_module(f'pytuflow.results.fm.units.{fpath.stem.lower()}')
        # available_classes.append(getattr(mod, class_pascal_case))
        # available_units.append(getattr(mod, 'SUB_UNIT_NAME'))


get_available_classes()


class Dat(Dat_):

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        for cls in available_classes:
            self.add_handler(cls)

