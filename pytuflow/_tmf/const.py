
# Import package constants
# noinspection PyPep8Naming
from . import cf as CONTROLFILE
# noinspection PyPep8Naming, PyUnusedImports
from . import inp as INPUT
# noinspection PyPep8Naming, PyUnusedImports
from . import db as DB

# Global library constants
UNKNOWN_TYPE = 'UNKNOWN'


def short_tuflow_type(tuflow_type: str) -> str:
    """Get the short type (TCF, TGC, TRFC, etc) from the CONTROLFILE type.
    
    Example

    ::


        >>>print(CONTROLFILE.TCF)
        TuflowControlFile
        
        >>>print(short_tuflow_type(CONTROLFILE.TCF))
        TCF

    Parameters
    ----------
    tuflow_type : str
        one of the CONTROLFILE type constants

    Returns
    -------
    str
        the short type of the CONTROLFILE type
    """
    try:
        return CONTROLFILE.SHORT_TYPES[tuflow_type]
    except KeyError:
        raise f'Tuflow type "{tuflow_type}" does not exist'
