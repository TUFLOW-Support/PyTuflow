import os
import sys
from pathlib import Path
import importlib

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'fm_to_estry'))

from fm_to_estry.helpers.available_dat_handlers import get_available_imports

dir_ = Path(__file__).parent.parent.parent / 'fm_to_estry' / 'fm_to_estry' / 'parsers' / 'units'
import_loc = 'fm_to_estry.parsers.units'
base_class = 'Handler'
for pck, name, cls_ in get_available_imports(dir_, base_class, import_loc):
    __import__(f'{import_loc}.{name}')
    globals()[cls_] = getattr(sys.modules[f'{import_loc}.{name}'], cls_)
