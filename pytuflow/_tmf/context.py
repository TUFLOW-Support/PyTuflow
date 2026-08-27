import logging
import re
import typing
from typing import Union

from .tfstrings.patterns import replace_exact_names
from .scope import Scope, ScopeList, VariableScope
from .tfpathlib import TuflowPath
from .tmf_types import ContextLike, VariableMap
from .event import EventDatabase
from .settings import TCFConfig


logger = logging.getLogger('pytuflow')


class Context:
    """Class for handling scenario/event/variable context for a given TUFLOW run state.

    Context can be initialised with

    * a list of arguments in the form of a TUFLOW batch file e.g. ['s1', 'EXG', 's2', '5m', '-e1', '100y']
    * a dictionary of arguments e.g. {'s1': 'EXG', 's2': '5m', 'e1': '100y'}
    * a list of scopes e.g. [Scope('SCENARIO', 'EXG'), Scope('SCENARIO', '5m'), Scope('EVENT', '100y')]

    The list of arguments can be unordered, however in most cases it is preferable to use an ordered list. Only in
    a small scope of tasks can the list be unordered.
    """

    def __init__(self, context: ContextLike = (), config: TCFConfig = None):
        """
        Parameters
        ----------
        context : ContextLike
            The context object can be initialised with a list of arguments, a dictionary object or a list of scopes.
        """
        #: bool: Whether variables defined in the TEF have been loaded into the context object
        self.events_loaded = False
        #: EventDatabase: An event database object that contains the events for the context object.
        self.event_db = EventDatabase()
        #: TCFConfig: Configuration object for the TUFLOW control file.
        self.config = config if config is not None else TCFConfig()
        #: list[str]: A list of arguments that the context object was initialised with.
        self.context_args = []
        #: var_map: dict[str, str]: A dictionary object of contextual variables
        self.var_map = {}
        #: dict[str, str]: A dictionary of event variables that are loaded from the event database.
        self.event_variables = {}
        if isinstance(context, dict):
            self.load_context_from_dict(context)
        elif isinstance(context, str):
            self.load_context_from_args(context.split())
        #: bool: Whether user defined variables have been loaded into the context object
        self.var_loaded = False
        if not self.events_loaded:
            self.load_events(self.config.event_db)

    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        return None

    @property
    def available_scopes(self) -> ScopeList:
        """Property that returns a ScopeList of all available scopes in the context object.
        e.g.

        if :code:`s1 = EXG` and :code:`s2 = 5m`, then the available scopes
        will be :code:`ScopeList([Scope('SCENARIO', 'EXG'), Scope('SCENARIO', '5m')])`

        Returns
        -------
        ScopeList
            A list of all available scopes in the context object.
        """
        avail_scopes = ScopeList()
        for a in ['S', 'E']:
            avail_scopes.extend([Scope(a, s) for s in self._create_list(a)])
        for k in self.event_variables.keys():
            avail_scopes.append(Scope('EVENT DEFINE', k))
        for k, v in self.var_map.items():
            if re.findall(r'^[_a-z]', k):
                continue
            if re.findall(r'^[es]\d?$', k, flags=re.IGNORECASE) or k == 'event_variables':
                continue
            if isinstance(v, list):
                for x in v:
                    avail_scopes.append(Scope('VARIABLE', x, var='<<{0}>>'.format(k)))
            else:
                avail_scopes.append(Scope('VARIABLE', v, var='<<{0}>>'.format(k)))
        return avail_scopes

    def is_empty(self) -> bool:
        """Returns whether the context object is empty. Will not count variables as if they are not
        controlled by scenarios/events, then they don't need context to be resolved.

        Returns
        -------
        bool
            True if the context object is empty, False otherwise.
        """
        return len(self._create_list('S')) == 0 and len(self._create_list('E')) == 0

    def load_context_from_dict(self, context: dict) -> None:
        """Public function that will load the context object from a dictionary.

        Parameters
        ----------
        context : dict
            A dictionary of context values. The keys should be the variable names and the values should be the
            variable values.
        """
        self.context_args = sum([[k, v] for k, v in context.items()], [])
        for i, key in enumerate(self.context_args[::2]):
            if key and key[0] != '-':
                self.context_args[i * 2] = '-{0}'.format(key)
        context = self._convert_to_lower_keys(context)
        self._parse_context_from_dict(context, 's')
        self._parse_context_from_dict(context, 'e')
        self.load_events(self.config.event_db)

    def load_context_from_args(self, args) -> None:
        """Public function that will load the context from a list or args.

        Parameters
        ----------
        args : list
            A list of arguments that will be used to initialise the context object.
        """
        context = {}
        self.context_args = args[:]
        self._parse_context_from_args(args, 's', context)
        self._parse_context_from_args(args, 'e', context)
        self.load_context_from_dict(context)

    def load_variables(self, var_map: VariableMap):
        """Public function that will load variables into the context object. The variable map should be a dictionary
        of the variable names and the variable values.

        Parameters
        ----------
        var_map : dict
            A dictionary of variable names and their values.
        """
        if var_map is None:
            return
        for key, value in var_map.items():
            key = key.upper()
            setattr(self, key, value)
            self.var_map[key] = value
        self.var_loaded = True

    def load_events(self, event_db: EventDatabase) -> None:
        """Public function that will load an event database into the context object.

        Parameters
        ----------
        event_db : EventDatabase
            An event database object that will be used to load the events into the context object.
        """
        if not event_db:
            return
        self.event_db = event_db
        for inp in event_db.inputs:
            if self.in_context_by_scope(inp.scope):
                self.event_variables[inp.event_var.upper()] = inp.event_value
        event_list = self._create_list('E')
        for e in event_list:
            event = event_db.get(e)
            if event is None:
                logger.warning('Event "{0}" not found in event database'.format(e))
                continue
            if not event_db.inputs:  # fallback incase event database is manually generated by user
                for k, v in event.items():
                    self.event_variables[k.upper()] = v
        self.events_loaded = True

    def in_context_by_scope(self, req_scope: ScopeList) -> bool:
        """Mutually exclusive will treat IF/ELSE IF blocks as mutually exclusive.

        i.e. in the example below, D01 and D02 are mutually exclusive, if D01 and D02 are both specified
        only the D01 block will be run. Setting mutually_excl to False will trigger both blocks, i.e. maybe the user
        wants to copy all input files for both scenarios. ELSE blocks will always be treated as mutually exclusive.

        ::

            IF Scenario == D01
                ! do something
            Else IF Scenario == D02
                ! do something else
            END IF

        Parameters
        ----------
        req_scope : ScopeList
            A list of scopes that are required to be in the context object.

        Returns
        -------
        bool
            True if the context object contains the required scopes, False otherwise.
        """
        if req_scope is None or Scope('GLOBAL') in req_scope:
            return True

        for s in req_scope:
            if not s.resolvable():  # "Start 1D Domain" or "Define Output Zone" etc.
                continue
            if not self.available_scopes.contains(s, neg=False) and not s.is_neg():
                return False
            elif self.available_scopes.contains(s, neg=False) and s.is_neg():
                return False
            elif isinstance(s, VariableScope) and '<<' in s.names[0]:
                return False

        return True

    def translate(self, item: typing.Any) -> typing.Any:
        """Translates input string into a resolved string.
        It does this by replacing all variables with their values.

        Parameters
        ----------
        item : typing.Any
            The input string that will be translated.

        Returns
        -------
        typing.Any
            The translated string.
        """
        if not isinstance(item, str) and not isinstance(item, TuflowPath):
            return item
        name_ = str(item)
        name_ = replace_exact_names('<<.+?>>', self.var_map, name_)
        for key, value in self.event_variables.items():
            name_ = replace_exact_names(re.escape(key), self.event_variables, name_)
        name_ = replace_exact_names('<<.+?>>', self.var_map, name_)  # run this again since event source could have <<~e~>> variables in it
        return name_

    def translate_result_name(self, tcf_name: str) -> str:
        """Translates the TCF file name into a string replacing all variables with their values.

        Parameters
        ----------
        tcf_name : str
            The TCF file name that will be translated.

        Returns
        -------
        str
            The translated TCF file name.
        """
        a = [x.strip('-') for x in self.context_args]
        a_upper = [x.upper() for x in a]
        a_used = []
        name_ = TuflowPath(tcf_name).stem
        for match in re.findall(r'~[SsEe]\d?~', tcf_name):
            var = match.upper()[1:-1]
            i = 0
            if var in a_upper:
                i = a_upper.index(var)
            elif var == 'E' and 'E1' in a_upper:
                i = a_upper.index('E1')
            elif var == 'E1' and 'E' in a_upper:
                i = a_upper.index('E')
            elif var == 'S' and 'S1' in a_upper:
                i = a_upper.index('S1')
            elif var == 'S1' and 'S' in a_upper:
                i = a_upper.index('S')
            else:
                continue
            val = self.context_args[i + 1]
            name_ = name_.replace(match, val)
            if var not in a_used:
                a_used.append(var)
        for var in reversed(a_used):
            i = a_upper.index(var)
            a.pop(i + 1)
            a.pop(i)
        e_list = []
        s_list = []
        for i, var in enumerate(a[::2]):
            val = a[i * 2 + 1]
            if var.upper()[0] == 'E':
                e_list.append(val)
            elif var.upper()[0] == 'S':
                s_list.append(val)
        for i, val in enumerate(e_list):
            if i == 0:
                name_ = f'{name_}_{val}'
            else:
                name_ = f'{name_}+{val}'
        for i, val in enumerate(s_list):
            if i == 0:
                name_ = f'{name_}_{val}'
            else:
                name_ = f'{name_}+{val}'
        return name_

    def is_resolved(self, item: typing.Any) -> bool:
        """Checks whether item has been resolved (to the best of its ability). Event variable names are custom and
        is not always possible to know whether they have been resolved or not.

        Parameters
        ----------
        item : typing.Any
            The item that will be checked for resolution.

        Returns
        -------
        bool
            True if the item has been resolved, False otherwise.
        """
        if not isinstance(item, str) and not isinstance(item, TuflowPath):
            return True
        if re.findall(r'<<.+?>>', str(item)):
            logger.warning('Item could not be resolved by context: {}'.format(str(item)))
            return False
        for key in self.event_db.event_variables():
            if key and key in str(item):
                logger.warning('Item could not be resolved by context: {}'.format(str(item)))
                return False

        return True

    def _parse_context_from_dict(self, context: dict, identifier: str) -> None:
        """Initialises the context object from a dictionary.
        e.g. :code:`{'s1': 'EXG', 's2': '5m', 'e1': '100y'}`
        """
        s = context.get(identifier, None)
        s1 = '{0}1'.format(identifier)
        if s and context.get(s1, None):
            raise ValueError('Context cannot have both {0} and {1}'.format(s, s1))
        if s and isinstance(s, list) and len(s) > 1:
            setattr(self, identifier.upper(), s)
            self.var_map[identifier.upper()] = s
        elif s or context.get(s1, None):
            for i in range(1, 10):
                if i == 1 and s:
                    key = s1
                    if isinstance(s, list):
                        value = s[0]
                    else:
                        value = s
                else:
                    key = '{0}{1}'.format(identifier, i)
                    value = context.get(key, None)
                if value:
                    if hasattr(self, key.upper()):
                        logger.error('Context could not be initialised; context already has attribute {}'.format(key))
                        raise ValueError('Context already has attribute {0}'.format(key))
                    setattr(self, key.upper(), value)
                    self.var_map[key.upper()] = value

    @staticmethod
    def _parse_context_from_args(args: list[str], identifier: str,
                                 context: dict[str, Union[str, list[str]]]) -> None:
        """Initialises the context object from a list of arguments for a specific identifer (e.g. 's' or 'e').
        This routine will return a dictionary of the variable name and the variable value.
        e.g. :code:`['s1', 'EXG', 's2', '5m'] = {'s1': 'EXG', 's2': '5m'}`

        This routine will consider both ordered and unordered lists:
        e.g. :code:`['s', 'EXG', 's', '5m'] = {'s': ['EXG', '5m']}`
        """
        while args:
            a = args[0]
            args = args[1:]
            if re.findall(r'-?[{0}{1}]\d?'.format(identifier.upper(), identifier.lower()), a):
                if a.lower() in ['-{0}'.format(identifier), identifier]:
                    if context.get(identifier) and not isinstance(context[identifier], list):
                        context[identifier] = [context[identifier], args[0]]
                    elif context.get(identifier):
                        context[identifier].append(args[0])
                    else:
                        context[identifier] = args[0]
                else:
                    if a.upper().strip('-') in [x.upper() for x in context.keys()]:
                        raise ValueError('Duplicate context values for {0}'.format(a.lower().strip('-')))
                    context[a.lower().strip('-')] = args[0]
                args = args[1:]
            else:
                args = args[1:]
        if context.get(identifier) and not isinstance(context[identifier], list):
            context['{0}1'.format(identifier)] = context[identifier]
            del context[identifier]

    @staticmethod
    def _convert_to_lower_keys(d: dict[str, typing.Any]) -> dict[str, typing.Any]:
        d_out = {}
        for k, v in d.items():
            if re.findall(r'^[EeSs]\d?$', k):
                d_out[k.lower()] = v
            else:
                d_out[k] = v
        return d_out

    def _create_list(self, identifier: str) -> list[str]:
        """Creates a list of all the available scope names given an identifier (e.g. 's', 'e')

        This will create an unordered list, so s1, s2 names will be return as ['5m', 'EXG'].
        """

        if not hasattr(self, identifier):
            list_ = [getattr(self, '{0}{1}'.format(identifier, i)) for i in range(9) if
                      hasattr(self, '{0}{1}'.format(identifier, i)) and getattr(self, '{0}{1}'.format(identifier, i))]
        else:
            list_ = getattr(self, identifier)
        return list_


