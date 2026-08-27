import typing


if typing.TYPE_CHECKING:
    from ..abc.t_cf import T_ControlFile
    from ..context import Context
    from ..event import EventDatabase


class ControlFileUniversalMixin:

    def tef(self, *args, **kwargs) -> 'T_ControlFile':
        # doc deferred to subclasses
        return self._find_control_file('event file', **kwargs)

    def event_database(self, context: 'Context' = None) -> 'EventDatabase':
        """Returns the EventDatabase object.

        If more than one EventDatabase object exists, a Context object must be provided to resolve to the correct
        EventDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct EventDatabase object. Not required unless more than one
            EventDatabase file object exists.

        Returns
        -------
        EventDatabase
            The EventDatabase object.

        Raises
        ------
        KeyError
            If the Event File is not found in the control file.
        ValueError
            If more than one Event File is found and no context is provided to resolve the correct one or if
            the context does not resolve into a single Event File.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.event_database()
        {'Q100': {'_event1_': '100yr'},
         'QPMF': {'_event1_': 'PMFyr'},
         '2hr': {'_event2_': '2hr'},
         '4hr': {'_event2_': '4hr'}}
        """
        tef = self._find_control_file('event file', context)
        return tef.event_database()
