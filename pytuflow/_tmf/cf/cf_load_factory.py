import logging
from ..logging_ import set_logging_level


logger = logging.getLogger('pytuflow')


class ControlFileLoadMixin:
    """Mixin to handle any load hooks and behaviour.
    
    Handles instance creation requirements on ControlFileBuildState creation (TCF,
    TGC, TBC, etc). Should only receive args/kwargs in the constructor to allow
    MRO to resolve properly.
    
    Behaviour that is required prior to fully initialising and loading the
    ControlFileBuildState objects goes here. 
    """
    
    def __init__(self, *args, **kwargs):
        log_level = kwargs.pop('log_level', None)
        log_to_file = kwargs.pop('log_to_file', None)

        # If one of the logging kwargs has been provided call the setup function
        # noinspection PyUnreachableCode
        if log_level is not None or log_to_file is not None:
            log_level = 'WARNING' if log_level is None else log_level
            set_logging_level(log_level, log_to_file)

        super().__init__(*args, **kwargs)
