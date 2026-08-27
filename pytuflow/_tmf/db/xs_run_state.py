try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from ..cf.cf_run_state import ControlFileRunState
from ..abc.run_state import RunState
from ..abc.db import Database
from ..context import Context
from .xs import CrossSectionDatabase



class CrossSectionRunState(RunState, Database):
    """Run state class for cross-sections database."""

    def __init__(self, build_state: CrossSectionDatabase, context: Context, parent: ControlFileRunState):
        super(CrossSectionRunState, self).__init__(build_state, context, parent)
        self.bs = build_state
        self.fpath = self.bs.fpath
        self.loaded = self.bs.loaded
        self._driver = self.bs.driver.copy()

    def __repr__(self):
        if self.fpath:
            if self.fpath.exists():
                return '<{0}Context> {1}'.format(self.bs.__class__.__name__, self.fpath.name)
            return '<{0}Context> {1} (not found)'.format(self.bs.__class__.__name__, self.fpath.name)
        else:
            return '<DatabaseContext> (empty)'

    def _resolve_scope_in_context(self) -> None:
        if not self._driver.unresolved_xs:
            self._df = self.bs.df.to_df()
            return

        # cross-section attributes need some resolving
        self._df = pd.DataFrame()
        for xsid in self._driver.unresolved_xs.copy():
            xs = self._driver.cross_sections[xsid]
            for key, value in xs.attrs.copy().items():
                new_val = self.ctx.translate(value)
                if not self.ctx.is_resolved(new_val):
                    raise ValueError('Input has not been completely resolved - {0}'.format(value))
                xs.attrs[key] = new_val
            xs.load()
            self._driver.unresolved_xs.remove(xsid)

        self._df = self._driver.generate_df()

        self._index_to_file = {x.id: x.fpath for x in self._driver.cross_sections.values()}

