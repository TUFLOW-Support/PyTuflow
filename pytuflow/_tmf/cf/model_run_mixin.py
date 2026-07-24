import subprocess
import os
from pathlib import Path
import logging

from ..tmf_types import PathLike
from ..tuflowfv_binaries import TuflowBinaries, TuflowFVBinaries


logger = logging.getLogger('pytuflow')


class ModelRunMixin:

    def _run(self, model_fpath: str | Path, bin_path: str, ctx_args: list[str], add_tf_flags: list[str], *args, **kwargs):
        """Method for running the control file using the tuflow binary specified."""
        if 'creationflags' not in kwargs and os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
        args_ = [bin_path]
        args_.extend(ctx_args)
        args_.extend(add_tf_flags)
        args_.append(str(model_fpath))
        self.proc = subprocess.Popen(args_, *args, **kwargs)
        return self.proc

    @staticmethod
    def _find_tuflow_bin(binaries: TuflowBinaries, tuflow_bin: PathLike, prec: str) -> str:
        """Returns the path to the TUFLOW binary to use for the run."""
        if Path(tuflow_bin).is_file() and not Path(tuflow_bin).exists():
            logger.error('tuflow binary not found: {0}'.format(tuflow_bin))
            raise FileNotFoundError('tuflow binary not found: {0}'.format(tuflow_bin))
        elif not Path(tuflow_bin).is_file():
            if tuflow_bin not in binaries:
                # search for available tuflow versions in registered folders
                # do this only now (after checking explicitly registered binaries first)
                # just in case this is a slow step (network drives etc.)
                binaries.refresh_from_settings()
                if tuflow_bin not in binaries:
                    logger.error('TUFLOW binary version not found: {0}'.format(tuflow_bin))
                    raise KeyError('TUFLOW binary version not found: {0}'.format(tuflow_bin))
        tuflow_bin_ = str(tuflow_bin) if Path(tuflow_bin).is_file() else binaries[tuflow_bin]
        if prec.upper() in ['DP', 'IDP', 'DOUBLE']:
            p = Path(tuflow_bin_)
            if 'dp' not in p.stem.lower():
                tuflow_bin_ = p.parent / str(p.name).replace('SP', 'DP')
        elif prec.upper() not in ['SP', 'ISP', 'SINGLE']:
            logger.error('Unrecognised "prec" argument: {0}'.format(prec))
            raise AttributeError('Unrecognised "prec" argument: {0}'.format(prec))

        return str(tuflow_bin_)
