import logging
import re
import typing

from .scope import Scope


if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .inp.inputs import Inputs
    # noinspection PyUnusedImports
    from .abc.input import T_Input

logger = logging.getLogger('pytuflow')


class ScopeWriter:
    """Class to help manage scope blocks and indentation when writing to a file."""

    def __init__(self, active_scope_list: list[Scope] = (), incoming_scope_list: list[Scope] = ()):
        self.incoming_scope_list = incoming_scope_list.copy() if incoming_scope_list else []
        self.active_scope = None
        self.added_to_stack = False
        self._lost_focus = False
        if self.incoming_scope_list:
            self.active_scope = self.incoming_scope_list.pop(0)
        self.active_scope_list = active_scope_list if active_scope_list else []
        if self.active_scope:
            self.active_scope_list.append(self.active_scope)
            self.added_to_stack = True
        if self.active_scope is None and self.active_scope_list and self.active_scope_list[-1].is_neg():
            self.active_scope = self.active_scope_list[-1]
        self.idx = len(self.active_scope_list) - 1

    def else_or_else_if(self):
        if not self.active_scope:
            return False
        if self.active_scope.is_neg():
            return True
        if self.active_scope_list and self.active_scope_list[-1].is_neg() and self.active_scope.as_neg() != self.active_scope_list[-1]:
            return True
        if len(self.active_scope_list) > 1 and self.active_scope_list[-2].is_neg():
            return True
        return False

    def _else_(self):
        if not self.active_scope:
            return False
        return self.active_scope.is_neg()

    def _in_stack(self, scope_list: list[Scope]) -> bool:
        s = scope_list[self.idx] if len(scope_list) > self.idx else None
        return self.idx == -1 or (s == self.active_scope and not self._lost_focus) or self.active_scope.as_neg() == s

    def _build_from_negative_scope(self, scope_list: list[Scope]) -> bool:
        i = 0 if self.idx == -1 else self.idx + 1
        return len(scope_list) > i and scope_list[i].is_neg()

    @staticmethod
    def _input_scope(inp: 'T_Input') -> list[Scope]:
        # remove the global scope from the input scope list
        # noinspection PyTypeChecker
        scope_list = list(inp.scope)
        while Scope('Global') in scope_list:
            scope_list.remove(Scope('Global'))
        return scope_list

    def inputs(self, fo: typing.TextIO, inputs: 'Inputs'):
        if self.active_scope:
            # write the start of the scope (e.g "If Scenario == DEV")
            if self.else_or_else_if():
                if not self.active_scope.supports_else_if():
                    raise ValueError('{self.active_scope.type} does not support '
                                     'ELSE or ELSE IF, but found a negative scope')
                if self._else_():
                    fo.write(f'{self.indent(1)}Else\n')
                else:
                    fo.write(f'{self.indent(1)}Else {self.active_scope.to_string_start()}\n')
            else:
                fo.write(f'{self.indent(1)}{self.active_scope.to_string_start()}\n')

        i = -1
        while True:
            i += 1
            if i > 10_000:
                raise RuntimeError('ScopeWriter.inputs(): Too many iterations (>10,000), something has gone wrong. Check input scopes.')
            try:
                inp = inputs.next()
            except StopIteration:
                break

            scope_list = self._input_scope(inp)

            if self.active_scope_list == scope_list:  # in scope
                yield inp, self
            else:
                inputs.rewind(1)
                if self._in_stack(scope_list):  # if we're still in the same stack, continue building
                    if self.idx != -1 and self.idx < len(self.active_scope_list) and scope_list[self.idx].is_neg():
                        self.active_scope_list[self.idx] = scope_list[self.idx]
                    if self._build_from_negative_scope(scope_list):  # no corresponding starting scope, need to build this
                        i = 0 if self.idx == -1 else self.idx + 1
                        scope_list = [scope_list[i].as_pos()]
                        scope_writer = ScopeWriter(self.active_scope_list, scope_list)
                        yield from scope_writer.inputs(fo, inputs)
                        continue
                    scope_writer = ScopeWriter(self.active_scope_list, scope_list[self.idx + 1:])
                    yield from scope_writer.inputs(fo, inputs)
                    if scope_writer.else_or_else_if():
                        self._lost_focus = True
                else:
                     break

        # "else" / "else if" does not take ownership of writing the "end if" part
        if self.active_scope and not self.else_or_else_if():
            fo.write(f'{self.indent(1)}{self.active_scope.to_string_end()}\n')

        if self.added_to_stack:
            self.active_scope_list.pop()

    def write(self, text: str, header: bool = False) -> str:
        """Writes the text with the correct indentation. Try and leave as is if the current indent level
        is correct i.e. don't start replacing tabs with spaces.

        :code:`header` indicates whether the text is a header for a scope block (therefore should be indented less).

        Parameters
        ----------
        text : str
            The text to write.
        header : bool, optional
            Whether the text is a header for a scope block, by default False

        Returns
        -------
        str
            The text with the correct indentation.
        """
        if not text:  # only indent if at least '\n' is present
            return text

        i = 1 if header else 0
        curr_width = self.calc_existing_width(text)
        reqd_width = len(self.indent(i))
        if curr_width == reqd_width:
            return text
        else:
            return self.indent(i) + text.lstrip(' \t')

    def indent(self, i: int = 0) -> str:
        """Returns the current scope indentation.

        :code:`i` can be used to modify the indentation level (removes indent level by i)
        e.g. :code:`If Scenario == ..`
        will be considered inside a scope, but should not be indented because it is the header of that scope,
        so :code:`i = 1` to remove one level of indentation.
        """
        # return '    ' * (max(0, len(self.active_scope) - 1 - i))
        nindents = len([s for s in self.active_scope_list if not s.is_neg()])
        nindents += 1 if (self.active_scope and self.active_scope.is_neg()) or (self.active_scope_list and self.active_scope_list[-1].is_neg()) else 0
        return '    ' * (max(0, nindents - i))

    @staticmethod
    def calc_existing_width(text: str) -> int:
        """Calculates the width of the current indentation.

        Parameters
        ----------
        text : str
            The text to calculate the width of.

        Returns
        -------
        int
            The width of the current indentation.
        """
        i = re.search(r'\w', text)
        if not i:
            return 0
        indent = text[:i.start()]
        return indent.count(' ') + indent.count('\t') * 4

