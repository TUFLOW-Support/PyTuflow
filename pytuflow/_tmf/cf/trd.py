from .cf_build_state import ControlFileBuildState
from .cf_load_factory import ControlFileLoadMixin
from ..inp.inputs import Inputs
from ..tmf_types import PathLike
from ..tfpathlib import TuflowPath
from .. import const


class TRD(ControlFileLoadMixin, ControlFileBuildState):
    TUFLOW_TYPE = const.CONTROLFILE.TRD

    @staticmethod
    def get_inputs(cf: ControlFileBuildState, trd_path: PathLike) -> Inputs:
        trd = TuflowPath(trd_path)
        return Inputs([x for x in cf.inputs if x.trd == trd])
