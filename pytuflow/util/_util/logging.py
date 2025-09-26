"""pytuflow logging module.

:code:`pytuflow` uses the logging name 'pytuflow' (:code:`logging.getLogger('pytuflow')`) and by default
is written to the :code:`stdout` stream. The user can overwrite this by adding their own handler to the
:code:`pytuflow` logger prior to the :code:`pytuflow` library being initialised.
 
Examples
--------

Overriding the default :code:`pytuflow` logging handler by adding a custom handler:

::
 
 
    import logging

    logger = logging.getLogger('pytuflow')
    handler = CustomHandler()  # custom (or generic) handler setup by the user
    logger.addHandler(handler)
    
If no custom handlers are added, the default log level will be WARNING. This can be changed by calling
:func:`set_logging_level` with the desired log level. A file handler can also be added by passing in a directory
to :func:`set_logging_level`.

::


    import pytuflow.utils.logging as pytuflow_logging
    
    # change logging level to DEBUG
    pytuflow_logging.set_logging_level('DEBUG')
    
    # add a file handler
    pytuflow_logging.set_logging_level('DEBUG', '/path/to/log/folder')
"""

import logging
from pathlib import Path
from typing import Union

from ..._pytuflow_types import PathLike


def get_logger() -> logging.Logger:
    """Setup and return the standard logger used throughout the pytuflow package.

    To use, add the following lines to the top of any module in the library:

    Returns
    -------
    logging.Logger
        Logger instance with the name 'pytuflow'

    Example
    -------
    >>> import pytuflow
    >>> logger = pytuflow.get_logger()

    The logger instance can be used the same as any other standard python logger.
    """
    logger = logging.getLogger('pytuflow')

    # logger.addHandler(TMFHandler())
    return logger


def set_logging_level(
        level: Union['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'WARNING',
        log_to_file: PathLike = None) -> None:
    """Configure the default logging level for the "pytuflow" logger. The logger setting will be propagated to
    all submodule loggers.

    Has no impact if the user code has configured its own logger.
    if log_to_file is a valid filepath, a filehandler will also be set up and logs will be
    written to file.

    Parameters
    ----------
    level : str, optional
        keyword to set logging level. Default is 'WARNING'.
    log_to_file : str, optional
        folder path at which logs should be written.
    """
    if log_to_file:
        log_file = Path(log_to_file)
        log_file = log_file.joinpath('pytuflow_logs.log') if log_file.is_dir() else log_file.with_name('pytuflow_logs.log')

        pytuflow_logger = logging.getLogger("pytuflow")
        tmf_logger = logging.getLogger("tmf")
        fm2estry_logger = logging.getLogger("fm2estry")
        if log_file.parent.exists():
            fhandler = logging.FileHandler(log_file.resolve())
            fhandler.setFormatter(logging.Formatter(
                "%(asctime)s %(module)-25s %(funcName)-25s line:%(lineno)-4d %(levelname)-8s %(message)s"))
            fhandler.mode = "a"
            fhandler.maxBytes = 51200
            fhandler.backupCount = 2
            pytuflow_logger.addHandler(fhandler)
            tmf_logger.addHandler(fhandler)
            fm2estry_logger.addHandler(fhandler)
            try:
                pytuflow_logger.warning("Added a file handler to log results to: {}".format(log_to_file))
            except PermissionError:
                raise PermissionError('Unable to write to given log folder')
        else:
            pytuflow_logger.warning('File path for log file handler does not exist at {}'.format(log_to_file))
            raise ValueError('File path for log file handler does not exist at {}'.format(log_to_file))

    level = level.upper()
    level = level if level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] else 'WARNING'
    logging.getLogger('pytuflow').setLevel(level)
    logging.getLogger('tmf').setLevel(level)
    logging.getLogger('fm2estry').setLevel(level)
