import sys
try:
    import traceback
    has_traceback = True
except ImportError:
    traceback = 'traceback'
    has_traceback = False


class _Logging:
    """Compatibility class so routines can be copied from qgis tuflow plugin code."""

    @staticmethod
    def get_stack_trace():
        """Returns the stack trace as a string."""
        if has_traceback:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            return ''.join(traceback.extract_tb(exc_traceback).format()) + '{0}{1}'.format(exc_type, exc_value)
        return ''

    # noinspection PyMethodMayBeStatic
    def info(self, msg):
        """Prints a message to the console."""
        print(msg)

    # noinspection PyMethodMayBeStatic
    def warning(self, msg):
        """Prints a warning message to the console."""
        print('PyTUFLOW WARNING:', msg)

    # noinspection PyMethodMayBeStatic
    def error(self, msg, additional_info=None):
        """Prints an error message to the console."""
        print('PyTUFLOW ERROR:', msg)
        if additional_info:
            print(additional_info)


Logging = _Logging()
