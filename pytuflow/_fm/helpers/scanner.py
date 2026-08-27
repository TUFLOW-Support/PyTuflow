import typing

from ..parsers.units.handler import Handler


class ScanRule:

    def __init__(self, seq: typing.Sequence[str]) -> None:
        self.accept_first = False
        self.seq = seq
        self.next_unit = None  # output
        self._first = True

    def is_seq(self) -> bool:
        return isinstance(self.seq, (list, tuple)) and len(self.seq) > 1

    def check(self, unit: Handler, fwd: str, bck: str, excl_first: bool, excl_last: bool) -> bool:
        next_unit = getattr(unit, fwd)
        next_unit = next_unit[0] if next_unit else None
        if self.is_seq():
            if self._first and not excl_first:
                if self._unit_types_equal(unit, self.seq[0]):
                    return True
            # check sequence forward and backward to check unit isn't part of it
            cnt = len(self.seq)
            for i in range(cnt - 1, -1, -1):
                if not self._first and i != 0:
                    continue
                ibck, ifwd = i, cnt - i - 1
                units = self._recursive_walk(unit, None, ibck, bck) + [unit] + self._recursive_walk(unit, None, ifwd, fwd)
                if self._unit_type_lists_equal(units, self.seq):
                    if i == 0 and self.accept_first:
                        continue
                    self.next_unit = units[-1]
                    if excl_last:  # exclusive, don't include the last unit as valid
                        self.next_unit = getattr(units[-1], fwd)
                        self.next_unit = self.next_unit[0] if self.next_unit else None
                    self._first = False
                    return False
        else:
            if not self.seq:
                return True
            if isinstance(self.seq, (list, tuple)):
                self.seq = self.seq[0]
            if self._unit_types_equal(unit, self.seq):
                self.next_unit = next_unit
                return False

        return True

    def _recursive_walk(self, unit: Handler, unit_list: list[Handler], count: int, fwd: str) -> list:
        if unit_list is None:
            unit_list = []  # first call
        if len(unit_list) == count:
            return unit_list
        next_unit = getattr(unit, fwd)
        if next_unit:
            unit_list.append(next_unit[0])
        else:
            unit_list.append(None)
        return self._recursive_walk(unit_list[-1], unit_list, count, fwd)

    def _unit_types_equal(self, u1: Handler, u2: str) -> bool:
        if u1 is None or u2 is None:
            return False
        if '_' in u2:
            u2_type = u2.split('_')
        else:
            u2_type = (u2, '')
        if u1.type.upper() != u2_type[0].upper():
            return False
        if u2_type[1] and u1.sub_type.upper() != u2_type[1].upper():
            return False
        return True

    def _unit_type_lists_equal(self, unit_list1: typing.Sequence[Handler], unit_list2: typing.Sequence[str]) -> bool:
        """Second list is the expected list."""
        if len(unit_list1) != len(unit_list2):
            return False
        for u1, u2 in zip(unit_list1, unit_list2):
            if not self._unit_types_equal(u1, u2):
                return False
        return True


class Scanner:
    """
    Utility to help scan upstream and downstream of a given node/unit.

    The scanner uses a set of rules list[ScanRule] which it will use to determine whether to skip a
    given unit or not.
    e.g. When looking upstream for the next 'real' unit, you may wish to therefore skip INTERPOLATES, JUNCTIONS, etc.

    Rules can also be a sequence of unit types:
    e.g. an orifice is a 'real' unit, but you may still wish to skip it if it's upstream of a culvert as it is acting
    as a device to help with culvert inlets.
    """

    def __init__(self):
        self.unit = None
        self.rules = []
        self.check_first = False
        self.exclusive = True
        self._unit = None
        self._fwd = None
        self._bck = None

    def scan(self, unit: Handler, direction: str, rules: list[ScanRule] = None, check_first: bool = False,
             excl_first: bool = True, excl_last: bool = True) -> Handler:
        self.unit = unit
        self.rules = rules
        self.check_first = check_first
        self.excl_first = excl_first
        self.excl_last = excl_last
        if direction.lower() == 'upstream':
            self._fwd, self._bck = 'ups_units', 'dns_units'
        elif direction.lower() == 'downstream':
            self._fwd, self._bck = 'dns_units', 'ups_units'
        else:
            raise ValueError('Direction must be either "upstream" or "downstream"')
        return self._scan()

    def _scan(self) -> Handler:
        unit = self._starting_point()
        if not unit:
            return
        while True:
            next_unit = self._walk(unit)
            if not next_unit:
                break
            for rule in self.rules:
                rule.accept_first = True
            unit = next_unit
        return unit

    def _starting_point(self) -> Handler:
        if self.check_first:
            unit = self.unit
        else:
            next_unit = getattr(self.unit, self._fwd)
            if not next_unit:
                unit = None
            else:
                unit = next_unit[0]
        return unit

    def _walk(self, unit: 'Handler') -> 'Handler':
        for rule in self.rules:
            if not rule.check(unit, self._fwd, self._bck, self.excl_first, self.excl_last):
                return rule.next_unit
