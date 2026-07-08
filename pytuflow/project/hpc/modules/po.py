from string import Template

from ._base import HPCBaseModule


class POModule(HPCBaseModule):
    NAME = 'po'
    DISPLAY_NAME = 'Plot Output'
    _TEMPLATE_KEY = ''
    _OUTPUT_SUBDIR = ''
    _TCF_COMMAND = r''
    _TCF_COMMENTED_LHS = ''
    _TCF_INSERT_AFTER_LHS = ''
