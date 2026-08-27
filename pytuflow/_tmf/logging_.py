import logging
from pathlib import Path
import threading

lock = threading.Lock()

from .tmf_types import PathLike


class Singleton(type):
    """Base class for Singleton Types.
    
    Initial setup will lock the constructor to avoid duplication.
    Only one instance of each subclass can be created, it will be tracked in
    the _instances dict.
    """
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    

# noinspection DuplicatedCode
class WarningLog(metaclass=Singleton):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._warnings = []
        self._use_warnings = False
        
    def activate(self):
        """Store warnings."""
        self._use_warnings = True

    def deactivate(self):
        """Stop storing warnings.
        
        This is the default.
        """
        self._use_warnings = False
        
    def add(self, msg):
        """Add a warning to the warning list.
        
        :param msg:
            str - text to add to the warning list
        
        Warnings will only be added if _use_warning == True by calling the
        active() method.
        """
        if self._use_warnings:
            self._warnings.append(msg)
        
    def get_warnings(self):
        """Return a list of warning stored in the log.
        
        Return list - containing warning messages
        """
        return self._warnings
    
    def reset(self):
        """Delete all warnings stored in the list."""
        self._warnings = []
        
_WARNING_LOG = WarningLog()
"""Conveniance reference for use in this module.

There's no reason it can't be used elsewhere too, as it's a singleton anyway,
but it's possible cleaner for calling code to grab it themselves (i.e. using:
warning_log = WarningLog() or just WarningLog().activate()).
"""


class TMFHandler(logging.Handler):
    """Custom handler to intercept logging messages being emitted.
    
    Will be added to the logger created at the top of all modules to provide an
    access point for additional behaviour we want when logging. For example, can
    be used to track information that may be useful in other formats, such as a
    list of warning for the end user. It saves having to clutter the code with
    multiple logging, warning, etc calls.
    """
    def emit(self, record) -> None:
        """Override the default emit function to add custom calls.
        
        Need to be careful what you do in here or it's possible to cause a log
        message to fail or even create a deadlock. See here for further information:
        https://docs.python.org/3/library/logging.html#logging.Handler.emit

        Parameters
        ----------
        record : LogRecord
            logging module LogRecord containing log details
        """
        
        # Adds a message to the WarningLog instance (if active).
        # If a level of WARNING or higher is created, we can log it elsewhere.
        # Will only happen if 'warn_log' is added to the logging extras option, e.g:
        # extras={'warn_log': 'some message'}.
        # If the message is 'msg', the logging message will be used. If it is any
        # other string, the given string will be used. All other values will be 
        # ignored.  
        if record.levelno >= logging.INFO:
            warn_log = None
            try:
                warn_log = record.warn_log
            except (AttributeError, KeyError, ValueError, TypeError):
                pass

            if warn_log is None or not isinstance(warn_log, str):
                return

            msg = record.msg if warn_log == 'msg' else warn_log
            _WARNING_LOG.add(msg)

        
def set_logging_level(
        level: str = 'WARNING',
        log_to_file: PathLike = None) -> None:
    """Configure the default logging level for the "pytuflow" logger.
    
    Has no impact if the user code has configured its own logger.
    if log_to_file is a valid filepath, a filehandler will also be set up and logs will be
    written to file.

    Parameters
    ----------
    level : str
        keyword to set logging level.
    log_to_file : str
        folder path at which logs should be written.
    """
    if log_to_file:
        log_file = Path(log_to_file)
        log_file = log_file.joinpath('pytuflow_logs.log') if log_file.is_dir() else log_file.with_name('pytuflow_logs.log')

        logger = logging.getLogger("pytuflow")
        if log_file.parent.exists():
            fhandler = logging.FileHandler(log_file.resolve())
            fhandler.setFormatter(logging.Formatter("%(asctime)s %(module)-25s %(funcName)-25s line:%(lineno)-4d %(levelname)-8s %(message)s"))
            fhandler.mode = "a"
            fhandler.maxBytes = 51200
            fhandler.backupCount = 2
            logger.addHandler(fhandler)
            try:
                logger.warning("Added a file handler to log results to: {}".format(log_to_file))
            except PermissionError:
                raise PermissionError('Unable to write to given log folder')
        else:
            logger.warning('File path for log file handler does not exist at {}'.format(log_to_file))
            raise ValueError('File path for log file handler does not exist at {}'.format(log_to_file))

    level = level.upper()
    level = level if level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] else 'WARNING'
    logging.getLogger('pytuflow').setLevel(level)
    