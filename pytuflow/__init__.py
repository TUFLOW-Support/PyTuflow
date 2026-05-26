import os
import sys
import logging

# sys.path.append(os.path.join(os.path.dirname(__file__), '_fm_to_estry'))
sys.path.append(os.path.join(os.path.dirname(__file__), '_tmf'))

# Setup default logging handler for pytuflow logger.
# If the user has already configured a handler, this block is skipped.
pytuflow_logger = logging.getLogger('pytuflow')
if not pytuflow_logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(module)-30s line:%(lineno)-4d %(levelname)-8s %(message)s"))
    ch.setStream(sys.stdout)
    ch.setLevel(logging.WARNING)
    pytuflow_logger.addHandler(ch)


from .TUFLOW import *
from ._outputs import *
from ._tmf import *
from ._fm import GXY, FMDAT
from .util import TuflowBinaries, pytuflow_logging, misc


name = 'PyTuflow'
__version__ = '1.2-dev.1'
