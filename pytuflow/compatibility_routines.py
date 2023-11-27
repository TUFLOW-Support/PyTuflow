"""
Module to fill the gap for QGIS versions that don't yet have Python 3.9+

Copies routines largely from the convert_tuflow_model_gis_format suite and modifies where required to
make compatible. These routines are just too useful sometimes to re-write in the plugin (so only do this as
required).

Hopefully this will not grow too big and can be deprecated (and removed) sometime in the near future (fingers crossed).
"""

import os
import re
try:
    from pathlib import Path
except ImportError:
    from .pathlib_ import Path_ as Path
from logging_ import Logging
