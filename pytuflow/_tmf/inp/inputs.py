import logging
import itertools
import typing

from ..scope import Scope, GlobalScope, ScopeList
from ..abc.input import T_Input




logger = logging.getLogger('pytuflow')


class Inputs(list[T_Input], typing.Generic[T_Input]):

    def __init__(self, inputs=()):
        list.__init__(self)
        self._inputs = list(inputs)
        list.extend(self, [x for x in inputs if x])
        self._indexes = []
        self._iter_idx = 0

    def __repr__(self):
        return '{0}({1})'.format(self.__class__.__name__, [str(x) for x in self])

    def __deepcopy__(self, memo):
        return self

    def next(self):
        if self._iter_idx >= len(self._inputs):
            raise StopIteration('No more inputs to iterate over')
        inp = self._inputs[self._iter_idx]
        self._iter_idx += 1
        return inp

    def rewind(self, steps: int = 1):
        self._iter_idx -= steps

    def reset_iterator(self):
        """Reset the iterator index to the start."""
        self._iter_idx = 0

    def _known_scopes(self) -> list[Scope]:
        def flatten(arr: list[list]) -> list:
            return list(itertools.chain.from_iterable(arr))
        scopes = [x.scope for x in self if x.scope]
        if scopes:
            # noinspection PyTypeChecker
            scopes = [x for x in flatten(scopes) if x.known or isinstance(x, GlobalScope)]
        return scopes

    def inputs(self, include_hidden: bool = False) -> list[T_Input]:
        return self._inputs if include_hidden else self

    def index(self, inp: T_Input, include_hidden: bool = False, **kwargs) -> int:
        """Find the index of the input in the inputs list."""
        lst = [x.uuid for x in self._inputs] if include_hidden else [x.uuid for x in self]
        return lst.index(inp.uuid)

    def at_index(self, index: int, include_hidden: bool = False):
        return self._inputs[index] if include_hidden else self[index]

    def next_before(self, inp: T_Input, include_hidden: bool = False) -> T_Input:
        """Find the next input before the given input."""
        ind = self._inputs.index(inp)
        if ind == 0:
            raise ValueError('No previous input found')
        for i in range(ind - 1, -1, -1):
            if self._inputs[i] or include_hidden:
                return self._inputs[i]
        raise ValueError('No previous input found')

    def amend(self, old_inp, new_inp) -> None:
        ind = self._inputs.index(old_inp)
        i, j = self._indexes[ind]
        if i > -1:
            list.remove(self, old_inp)
            self._inputs.remove(old_inp)
            self._inputs.insert(j, new_inp)
            self._indexes[ind] = (-1, j)
        else:
            i = self.prev_valid(j)
            i = 0 if i == -1 else i + 1
            self._indexes[j] = (i, j)
            for i_ in range(j+1, len(self._indexes)):
                i2, j2 = self._indexes[i_]
                if i2 > -1:
                    self._indexes[i_] = (i2+1, j2)
            self._inputs.remove(old_inp)
            self._inputs.insert(j, new_inp)
            list.insert(self, i, new_inp)

    def append(self, inp) -> None:
        if inp.is_start_block() or inp.is_end_block():
            return

        self._inputs.append(inp)
        if inp:
            list.append(self, inp)

        # this section is so that this class can be used to help record changes to the inputs, recording the
        # index of each input as it is added (which may only be correct at the instance it is added, changing as soon
        # as the next input is added) - therefore allowing the ability to unwind in reverse order
        # only available via the 'append' method
        if hasattr(inp, 'parent') and inp.parent and hasattr(inp.parent, 'inputs') and hasattr(inp, 'uuid'):
            if inp.uuid in [x.uuid for x in inp.parent.inputs]:
                i = [x.uuid for x in inp.parent.inputs].index(inp.uuid)
            else:
                i = -1
            try:
                j = [x.uuid for x in inp.parent.inputs.inputs(include_hidden=True)].index(inp.uuid)
            except ValueError:
                j = -1
        else:
            i, j = -1, -1
        self._indexes.append((i, j))  # used for undoing later if needed

    def insert(self, ind, inp, after=False, hidden_index=False) :
        try:
            if inp.is_start_block() or inp.is_end_block():
                return
        except AttributeError:
            pass
        ref_inp = self._inputs[ind] if hidden_index else self[ind]
        i = self.index(ref_inp, include_hidden=True)
        if after:
            if inp:
                if ind < 0:
                    ind = len(self) - ind
                list.insert(self, ind + 1, inp)
            self._inputs.insert(i + 1, inp)
        else:
            if inp:
                list.insert(self, ind, inp)
            self._inputs.insert(i, inp)

    def extend(self, items) -> None:
        self._inputs.extend(items)
        for inp in items:
            if inp:
                list.append(self, inp)

    def remove(self, value):
        self._inputs.remove(value)
        if value:
            list.remove(self, value)

    def resolve_scopes(self) -> None:
        scopes = self._known_scopes()
        if not scopes:
            return
        for inp in self:
            inp.figure_out_file_scopes(ScopeList(scopes))

    def iter_indexes(self):
        for i, inp in enumerate(self._inputs):
            yield inp, self._indexes[i]

    def prev_valid(self, ind) -> int:
        for i in range(ind, -1, -1):
            i, j = self._indexes[i]
            if i > -1:
                return i
        return -1
