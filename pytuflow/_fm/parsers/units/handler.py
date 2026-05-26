import logging
import typing
from datetime import datetime
from typing import TextIO

import numpy as np

from ...helpers.reader import unpack_fixed_field
from ...converters.unit_converter_manager import UnitConverterManager
from ...output import OutputCollection

logger = logging.getLogger('pytuflow')


type2name = {
    float: 'float',
    int: 'int',
    str: 'str'
}


class BaseHandler:

    def __init__(self, parent: typing.Any = None) -> None:
        self.parent = parent

    def _sync_obj(self, other: 'BaseHandler') -> None:
        # push change from self into other
        if not other:
            return
        d = other.__dict__.copy()
        if '_sub_obj' in d:
            del d['_sub_obj']
        self.__dict__.update(d)

    def copy(self) -> 'BaseHandler':
        cls = self.__class__(self.parent)
        for attr in dir(self):
            if not attr.startswith('__'):
                val = getattr(self, attr)
                if callable(val):
                    continue
                if isinstance(val, list):
                    if attr in ['ups_units', 'dns_units']:  # don't want to deep copy these - will end up deep copying a lot of stuff
                        val = val.copy()
                    else:
                        try:
                            val = [x.copy() for x in val]  # list of objects that also need copying
                        except AttributeError:
                            val = val.copy()  # just normal list of scalars
                else:
                    try:
                        val = val.copy()  # dict, pandas, numpy
                    except AttributeError:
                        pass  # hopefully means it's just a scalar value
                setattr(cls, attr, val)
        return cls

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        """
        Set the id, uuid, and any other attributes.
        Try and follow naming convention from Flood Modeller Manual.
        Return a string buffer object containing the data to be read by pandas.
        """
        self.line = line
        self.fo = fo
        self.fixed_field_len = fixed_field_len
        self.line_no = line_no

    def read_line(self, labels: bool = False, data_length: int = 20) -> list[str]:
        if not self.fo or not self.fixed_field_len:
            return []
        self.line_no += 1
        if labels:
            return [x.strip() for x in unpack_fixed_field(self.fo.readline(), [self.fixed_field_len] * data_length)]
        return [x.strip() for x in unpack_fixed_field(self.fo.readline(), [10] * data_length)]

    def read_line_raw(self) -> str:
        self.line_no += 1
        return self.fo.readline()

    def _get_uid(self) -> str:
        if hasattr(self, 'type') and hasattr(self, 'sub_type') and hasattr(self, 'id'):
            return f'{self.type}_{self.sub_type}_{self.id}'
        return ''

    def _get_revision(self) -> int:
        if '#REVISION#' in self.line.upper():
            try:
                return int(self.line.upper().split('#REVISION#')[1].split(' ')[0].strip())
            except (ValueError, IndexError, TypeError):
                errmsg = f'Line No: {self.line_no}: Error reading revision number from line: {self.line}'
                logger.debug(errmsg)
                if hasattr(self, 'errors'):
                    self.errors.append(errmsg)
        return -1

    def _set_attrs(self, param: list[str], attrs: list[str], attr_types: list[object], ind: int = 0,
                   log_errors: typing.Union[bool, typing.Sequence[int]] = ()) -> None:
        for attr, typ in zip(attrs, attr_types):
            if not attr:
                continue
            try:
                setattr(self, attr, typ(param[ind]))
                if typ is str:
                    string = getattr(self, attr)
                    string = string.replace('\\', '').replace('/', '')
                    setattr(self, attr, string)
            except (ValueError, TypeError, IndexError):
                errmsg = f'Line No: {self.line_no}: Error reading "{attr}" as {type2name[typ]} at index #{ind} from parameters: {param}'
                if hasattr(self, 'uid') and self.uid:
                    errmsg = f'{self.uid}: {errmsg}'
                if log_errors == True or isinstance(log_errors, list) and ind in log_errors:
                    logger.error(errmsg)
                    if hasattr(self, 'errors'):
                        self.errors.append(errmsg)
                else:
                    logger.debug(errmsg)
                    if hasattr(self, 'checks'):
                        self.checks.append(errmsg)
            ind += 1

    def _set_attrs_str(self, param: list[str], attrs: list[str], ind: int = 0,
                       log_errors: typing.Union[bool, typing.Sequence[int]] = ()) -> None:
        self._set_attrs(param, attrs, [str] * len(attrs), ind, log_errors)

    def _set_attrs_int(self, param: list[str], attrs: list[str], ind: int = 0,
                         log_errors: typing.Union[bool, typing.Sequence[int]] = ()) -> None:
        self._set_attrs(param, attrs, [int] * len(attrs), ind, log_errors)

    def _set_attrs_float(self, param: list[str], attrs: list[str], ind: int = 0,
                         log_errors: typing.Union[bool, typing.Sequence[int]] = ()) -> None:
        self._set_attrs(param, attrs, [float] * len(attrs), ind, log_errors)


class SubHandler(BaseHandler):

    def post_load(self) -> None:
        pass


class Handler(BaseHandler):
    """Abstract base class for all unit handlers."""

    def __init__(self, *args, **kwargs) -> None:
        """ "type" and "TYPE" should be set by subclass. No arguments should be passed to this method."""
        super().__init__(*args, **kwargs)
        self.TYPE = 'unknown'
        self.line = None
        self.fo = None
        self.line_no = -1
        self.fixed_field_len = 10
        self.type = self.unit_type_name()
        self.sub_type = ''
        self.id = None  # id of the unit (populated in load method)
        self.uid = None  # id of the unit but includes the type which then creates a unique id (e.g. RIVER_SECTION_{id})
        self.dx = np.nan  # populated in load method
        self.bed_level = np.nan
        self.errors = []
        self.warnings = []
        self.checks = []
        self.ups_units = []
        self.dns_units = []
        self.ups_link_ids = []
        self.dns_link_ids = []
        self.x = np.nan
        self.y = np.nan
        self.wktgeom = None
        self.valid = False
        self.idx = -1
        self.converted = False
        self._sub_obj = None

    def __repr__(self) -> str:
        return self.uid

    @staticmethod
    def unit_type_name() -> str:
        return ''

    def write_check(self, lyr) -> None:
        if not self.wktgeom:
            return
        lyr.add_feature(self.wktgeom, {'uid': self.uid, 'dx': self.dx, 'bed_level': self.bed_level})

    def convert(self) -> OutputCollection:
        converter_manager = UnitConverterManager()
        converter_cls = converter_manager.find_converter(self)
        if converter_cls:
            converter = converter_cls(self)
            try:
                if converter_cls.__name__ != converter_manager.base_class:
                    self.converted = True
                return converter.convert()
            except Exception as e:
                logger.error(f'Error converting unit {self.uid}: {e}')
                return OutputCollection()


class Link:

    def __init__(self, id_: int, ups_unit: Handler, dns_unit: Handler) -> None:
        self.id = id_
        self.ups_unit = ups_unit
        self.dns_unit = dns_unit
        self.wktgeom = None

    def __repr__(self) -> str:
        return f'<Link {self.id} {self.ups_unit.uid} -> {self.dns_unit.uid}>'

    def __hash__(self):
        conn = f'{self.ups_unit.uid}_{self.dns_unit.uid}'
        return hash(conn)

    def __eq__(self, other):
        if not isinstance(other, Link):
            return False
        return self.ups_unit.uid == other.ups_unit.uid and self.dns_unit.uid == other.dns_unit.uid

    def write_check(self, lyr) -> None:
        if not self.wktgeom:
            return
        lyr.add_feature(self.wktgeom, {'id': self.id})
