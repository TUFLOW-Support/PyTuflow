import os
import re
import typing
from pathlib import Path

from ..tfpathlib import TuflowPath

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .line import TuflowLine


class TuflowValueExpander:
    """Class to help expands the rhs (value part) of a TUFLOW command.

    Using a class allows the logic to be moved out of the Command class. Some of the logic can be a bit fiddly,
    such as expanding GPKG layers, inserting variables, and handling relative paths.
    """

    def __init__(self, variables: dict[str, str] | typing.Callable[[str], str], database: Path | None,
                 deferred: bool = False, case_sensitivity: int = 0):
        self.value = None
        self.variables = variables
        self.database = database
        self.deferred = deferred
        self.case_sensitivity = case_sensitivity
        self._expanded_value = None

    def expand(self, value: str) -> str:
        """Expands the value by inserting variables and expanding GPKG layers. Does not expand relative paths."""
        self.value = value
        try:
            self._expanded_value = ' | '.join(self._expand())
        except ValueError as e:
            raise ValueError(f'Error expanding value "{self.value}": {e}') from e
        return self._expanded_value

    def expand_path(self, cf: Path, cmd: 'TuflowLine') -> str:
        return ' | '.join(self._expand_path(cf, cmd))

    def _insert_variables(self, value: str) -> str:
        """Inserts known variables into the line."""
        v = value
        for var_name, var_val in self.variables.items():
            if os.name != 'nt' and '\\' in var_val:
                var_val = var_val.replace('\\', '/')
            if f'<<{var_name.upper()}>>' in v.upper():
                v = re.sub(re.escape(rf'<<{var_name}>>'), var_val.replace('\\', '\\\\'), v, flags=re.IGNORECASE)
        return v

    def _expand(self) -> typing.Generator[str, None, None]:
        if callable(self.variables):
            val = self.variables(self.value)
        else:
            val = self._insert_variables(self.value)
        for p in val.split('|'):
            if p.strip().count('>>') > p.strip().count('<<'):
                yield from self._expand_line_gpkg(p.strip())
            else:
                yield p.strip()

    def _expand_path(self, cf: Path, cmd: 'TuflowLine') -> typing.Generator[str, None, None]:
        if self._expanded_value is None:
            raise Exception('Call expand() before expand_path()')
        val = self._expanded_value
        cnt = val.count('|') + 1
        for i, p in enumerate(val.split('|')):
            if cmd.is_number(p.strip(), cnt, i):
                yield p.strip()
                continue
            if p.strip().count('>>') > p.strip().count('<<'):
                yield self._expand_path_gpkg(p.strip(), TuflowPath(cf))
            elif cmd.looks_like_gpkg_layer_name(p, cnt, i) and self.database is not None and self.database != Path():
                yield f'{self.database} >> {p.strip()}'
            else:
                if cmd.should_add_mif_extension(p.strip(), cnt, i):
                    p = f'{p.strip()}.mif'
                # -cs1/-cs2 relax the final *filename* only, never the
                # name of an output/input directory supplied as a folder.
                is_folder = self.case_sensitivity != 0 and cmd.is_folder(p.strip(), cnt, i)
                if cf == Path():
                    yield str(TuflowPath(p.strip()) if self.deferred or is_folder else
                              TuflowPath.init_case_policy_path(p.strip(), case_sensitivity=self.case_sensitivity))
                else:
                    base = TuflowPath(cf).parent
                    yield str(base / p.strip() if self.deferred or is_folder else
                              base / TuflowPath.init_case_policy_path(
                                  p.strip(), base, self.case_sensitivity))

    def _expand_line_gpkg(self, part: str) -> typing.Generator[str, None, None]:
        from .. import gis
        db, lyr = self._split_lyr(part)
        if lyr.strip().lower() == 'all':
            if self.deferred or not Path(db).exists():
                yield f'{db} >> {lyr}'
                return
            for table in gis.get_all_layers_in_gpkg(db):
                yield f'{db} >> {table}'
        elif '&&' in lyr:
            for table in lyr.split('&&'):
                yield f'{db} >> {table.strip()}'
        else:
            yield f'{db} >> {lyr}'

    def _expand_path_gpkg(self, part: str, cf: TuflowPath) -> str:
        db, lyr = self._split_lyr(part)
        if cf != Path():
            base = TuflowPath(cf).parent
            db = base / db if self.deferred else base / TuflowPath.init_case_policy_path(
                db, base, self.case_sensitivity)
        return f'{db} >> {lyr}'

    def _split_lyr(self, part: str) -> tuple[str, str]:
        i = self._find_split(part)
        db = part[:i].strip()
        lyr = part[i + 2:].strip()
        return db, lyr

    @staticmethod
    def _find_split(part: str) -> int:
        v = part
        k = 0
        while '<<' in v:
            i = v.index('<<')
            i2 = v.index('>>')
            if i > i2:
                break
            if '>>' not in v[i:]:
                raise ValueError(f'Unbalanced "<< >>" in value: {part}')
            j = v.index('>>', i)
            v = v[j + 2:]
            k += j + 2
        return v.index('>>') + k
