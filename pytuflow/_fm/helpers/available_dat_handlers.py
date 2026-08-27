import logging
import importlib
import os
import re
import sys
import typing
from pathlib import Path



logger = logging.getLogger('pytuflow')


def find_handler_class(fpath: Path, all_classes: list[str]) -> str:
    cls_regex = r'(?:(?:\w+,\s?)?{0}(?:,\s?\w+)?)'.format('|'.join(all_classes))
    with fpath.open() as f:
        for line in f:
            line.split('#')[0].strip()
            if 'class' in line:
                cls = re.findall(fr'class \w+\({cls_regex}\):', line)
                if cls:
                    return cls[0].split('(')[0].split('class')[1].strip()


def get_available_classes(dir_: Path, base_class: str, import_loc: str) -> list[typing.Any]:
    units_dir = dir_
    classes = [base_class]
    length = 0
    length_ = len(classes)
    available_classes = []
    while length != len(classes):
        length = length_
        for fpath in units_dir.glob('*.py'):
            cls = find_handler_class(fpath, classes)
            if cls:
                if cls not in classes:
                    try:
                        mod = importlib.import_module(f'.{fpath.stem.lower()}', import_loc)
                        cls_ = getattr(mod, cls)
                        available_classes.append(cls_)
                        classes.append(cls)
                        yield cls_
                    except ImportError as e:
                        logger.error(f'{e}')
                        # logger.error(f'Error importing {cls} from {fpath.stem.lower()}')
        length_ = len(classes)


def get_available_imports(dir_: Path, base_class: str, import_loc: str) -> list[typing.Any]:
    """Same as above but returns the import loc, the file name, and the class name."""
    units_dir = dir_
    classes = [base_class]
    length = 0
    length_ = len(classes)
    available_classes = []
    while length != len(classes):
        length = length_
        for fpath in units_dir.glob('*.py'):
            cls = find_handler_class(fpath, classes)
            if cls:
                if cls not in classes:
                    try:
                        mod = importlib.import_module(f'.{fpath.stem.lower()}', import_loc)
                        cls_ = getattr(mod, cls)
                        available_classes.append(cls_)
                        classes.append(cls)
                        yield import_loc, fpath.stem.lower(), cls
                    except ImportError as e:
                        logger.error(f'{e}')
                        # logger.error(f'Error importing {cls} from {fpath.stem.lower()}')
        length_ = len(classes)
