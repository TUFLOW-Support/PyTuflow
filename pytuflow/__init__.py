import os
import sys
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), 'fm_to_estry'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'tmf'))

# setup logging from various modules
tmf_logger = logging.getLogger('tmf')
fm_to_estry_logger = logging.getLogger('fm2estry')
pytuflow_logger = logging.getLogger('pytuflow')
if not pytuflow_logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(module)-30s line:%(lineno)-4d %(levelname)-8s %(message)s"))
    ch.setStream(sys.stdout)
    ch.setLevel(logging.WARNING)
    tmf_logger.addHandler(ch)
    fm_to_estry_logger.addHandler(ch)
    pytuflow_logger.addHandler(ch)
else:  # add pytuflow handlers to the tmf and fm2estry loggers if they aren't there already
    for hnd in pytuflow_logger.handlers:
        if hnd not in tmf_logger.handlers:
            tmf_logger.addHandler(hnd)
        if hnd not in fm_to_estry_logger.handlers:
            fm_to_estry_logger.addHandler(hnd)


from .TUFLOW import *


name = 'PyTuflow'
__version__ = '0.0.62'
