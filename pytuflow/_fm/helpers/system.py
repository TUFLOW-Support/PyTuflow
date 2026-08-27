import os
import sys


def set_environment() -> None:
    """
    Set environment variables for compiled library or Python interpreter.

    :return: None
    """
    if os.path.basename(sys.executable.lower()) == 'fm_to_estry.exe':
        exeDir = os.path.dirname(sys.executable.lower())
        os.environ['PROJ_LIB'] = os.path.join(exeDir, '_internal', 'osgeo', 'data', 'proj')
    else:
        pass
        # sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fm_units'))
