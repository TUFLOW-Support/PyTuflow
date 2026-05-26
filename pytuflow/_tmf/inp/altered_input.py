import itertools
from typing import TYPE_CHECKING
from uuid import UUID

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from ..abc.input import Input
from ..abc.bld_state import BuildState
from .inp_build_state import InputBuildState
from .comment import CommentInput

if TYPE_CHECKING:
    from ..cf.cf_build_state import ControlFileBuildState
    from ..db.db_build_state import DatabaseBuildState

class AlteredType:

    def __init__(self, bs: BuildState, i: int, j: int, uuid: UUID, change_type: str, *args, **kwargs):
        super().__init__()
        self.parent = bs.parent
        #: UUID: UUID identifier of the AlteredType object. Not necessarily unique to this object, but is unique to a single change and can be used to group changes together.
        self.uuid = uuid
        #: int: Index of the input in the parent control file's valid input list. Set to -1 if the input is not in the valid list.
        self.i = i
        #: int: Index of the input in the parent control file's input list, including hidden inputs.
        self.j = j
        #: str: Identifier type of the change that was made to the input.
        self.change_type = change_type


class AlteredInput(AlteredType, Input):

    def __init__(self, inp: InputBuildState, i: int, j: int, uuid: UUID, change_type: str, *args, **kwargs):
        super().__init__(inp, i, j, uuid, change_type)
        #: Input: A reference to the input that was altered
        self.input = inp
        #: UUID: UUID of the input that was altered.
        self.inp_uuid = inp.uuid
        #: ScopeList: List of scopes for the input that was altered.
        self.scope = inp.scope
        self.parent: ControlFileBuildState | None = inp.parent
        self.trd = inp.trd
        self._command = inp.command()

    def __repr__(self):
        return '<{0} {1}> {2}'.format(__class__.__name__, self.change_type, self._command)

    def undo(self):
        raise NotImplementedError('undo() must be implemented by subclass')

    def _get_indexed_input(self) -> InputBuildState:
        """Returns the input from the parent control file that this AlteredInput refers to.

        The input is required to still be present in the control file. It is also only guaranteed to work if the
        altered input is at the top of the altered input stack i.e. added or removed inputs above this in the
        altered input stack will cause the indexing to be incorrect.

        Returns
        -------
        InputBuildState
            The input from the parent control file.
        """
        if not self.parent:
            raise ValueError('AlteredInput has no parent control file, cannot get indexed input.')
        if self.i >= 0:
            return self.parent.inputs[self.i]
        else:
            return self.parent.inputs.at_index(self.j, include_hidden=True)


class AlteredInputUpdatedValue(AlteredInput):

    def undo(self):
        self.input.rhs = self._command.value_orig


class AlteredInputUpdatedCommand(AlteredInputUpdatedValue):

    def undo(self):
        self.input.lhs = self._command.command_orig


class AlteredInputAddedInput(AlteredInput):

    def undo(self):
        self.parent.inputs.remove(self.input)


class AlteredInputRemovedInput(AlteredInput):

    def undo(self):
        inputs = self.parent.inputs.inputs(include_hidden=True)
        if inputs and 0 <= self.j < len(inputs):
            ref_inp = self.parent.inputs.at_index(self.j, include_hidden=True)
            self.input = self.parent.insert_input(ref_inp, self._command.original_text)
        else:
            self.input = self.parent.append_input(self._command.original_text)


class AlteredInputCommentOut(AlteredInput):

    def __init__(self, inp: CommentInput, i: int, j: int, uuid: UUID, change_type: str, *args, **kwargs):
        self.input: CommentInput = inp
        super().__init__(inp, i, j, uuid, change_type, *args, **kwargs)

    def undo(self) -> None:
        self.input = self.parent.uncomment(self.input)


class AlteredInputUncomment(AlteredInput):

    def undo(self) -> None:
        self.input = self.parent.comment_out(self.input)


class AlteredInputSetScope(AlteredInput):

    def undo(self):
        self.input.scope = self.scope


class AlteredDatabase(AlteredType):

    def __init__(self, db: 'DatabaseBuildState', i: int, j: int, uuid: UUID, change_type: str, prev_df: pd.DataFrame):
        super().__init__(db, i, j, uuid, change_type)
        self.db = db
        self.parent = db
        self.df = prev_df.copy(deep=True)

    def undo(self):
        self.db.recording_changes = False  # stop recording changes while undoing
        self.db.df = self.df
        self.db.recording_changes = True


def get_altered_input_class(change_type: str) -> type[AlteredType]:
    """Returns the appropriate AlteredInput subclass based on the change type."""
    if change_type == 'update_value':
        return AlteredInputUpdatedValue
    elif change_type == 'update_command':
        return AlteredInputUpdatedCommand
    elif change_type == 'add_input':
        return AlteredInputAddedInput
    elif change_type == 'remove_input':
        return AlteredInputRemovedInput
    elif change_type == 'set_scope':
        return AlteredInputSetScope
    elif change_type == 'comment_out':
        return AlteredInputCommentOut
    elif change_type == 'uncomment':
        return AlteredInputUncomment
    elif change_type == 'database':
        return AlteredDatabase
    else:
        raise ValueError(f'Unknown change type: {change_type}')


class AlteredInputs:

    def __init__(self):
        self._updated_inputs = [[]]  # 2D array to store altered input in blocks based on when write() was last called
        self._block = False

    def __repr__(self):
        updated_inputs = list(itertools.chain.from_iterable(self._updated_inputs))
        lim = 10
        if len(updated_inputs) > lim:
            updated_inputs = updated_inputs[:lim] + ['...']
        return f'<AlteredInputs: {len(updated_inputs)}> {updated_inputs}'

    def add(self, inp: 'BuildState', i: int, j: int, uuid, change_type: str, *args, **kwargs):
        if not self._block:
            cls = get_altered_input_class(change_type)
            ac = cls(inp, i, j, uuid, change_type, *args, **kwargs)
            self._updated_inputs[-1].append(ac)

    def undo(self, cf: 'ControlFileBuildState', reset_children: bool, updated_inputs: list = None) -> list[AlteredInput]:
        self._block = True  # so changes aren't recorded while undoing
        inputs = []

        was_clean = False
        i = len(self._updated_inputs) - 1
        if updated_inputs is None:
            updated_inputs = self._updated_inputs[-1]
            if not updated_inputs:
                was_clean = True
                updated_inputs = []
                while not updated_inputs and i >= 0:
                    updated_inputs = self._updated_inputs[i]
                    i -= 1

        if updated_inputs:
            i = len(updated_inputs) - 1
            while True:
                if updated_inputs[i].parent != cf and not reset_children:
                    i -= 1
                    if i < 0:
                        return inputs
                else:
                    break
            ac = updated_inputs.pop(i)
            inputs = [x for x in updated_inputs[::-1] if x.uuid == ac.uuid]
            inputs.insert(0, ac)
        cfs = []
        if inputs:
            for ac in inputs:
                if ac.parent != cf and not reset_children:
                    continue
                if ac.parent not in cfs:
                    cfs.append(ac.parent)
                ac.undo()
                if ac in self._updated_inputs:
                    updated_inputs.remove(ac)
                if ac.change_type != 'database':
                    try:
                        inp = ac.parent.input(ac.inp_uuid)
                        if inp.uuid not in [x.inp_uuid for x in updated_inputs]:
                            inp.dirty = False
                    except KeyError:
                        pass
                else:
                    if ac.parent not in [x.parent for x in updated_inputs]:
                        ac.parent.dirty = False
        self._block = False
        if not updated_inputs and not was_clean:
            self.set_clean(cf)
            for cf_ in cfs:
                self.set_clean(cf_)
            if cf.tcf and cf != cf.tcf:
                if not self.is_dirty(cf.tcf):
                    self.set_clean(cf.tcf)

        return inputs

    def reset(self, cf: 'ControlFileBuildState', reset_children: bool) -> list[AlteredInput]:
        reset_inputs = []
        updated_inputs = self._updated_inputs.pop()
        while True:
            inputs = self.undo(cf, reset_children, updated_inputs)
            if not inputs:
                break
            reset_inputs.extend(inputs)
        return reset_inputs

    def is_dirty(self, cf: 'ControlFileBuildState'):
        for ac in self._updated_inputs[-1]:
            if ac.parent == cf:
                return True
        return False

    @staticmethod
    def set_clean(cf: 'ControlFileBuildState'):
        from ..db.db_build_state import DatabaseBuildState
        if isinstance(cf, DatabaseBuildState):
            return
        for inp in cf.inputs:
            if inp.dirty:
                inp.dirty = False
        cf.dirty = False

    def clear(self):
        for ac in self._updated_inputs[-1]:
            if not isinstance(ac, AlteredDatabase):
                for inp in ac.parent.inputs:
                    inp.dirty = False
            ac.parent.dirty = False
            ac.parent.tcf.dirty = False
        self._updated_inputs.append([])
        # self._updated_inputs.clear()
