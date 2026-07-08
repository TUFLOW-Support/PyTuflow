from string import Template

from ._base import HPCBaseModule


class SGSModule(HPCBaseModule):
    NAME = 'sgs'
    DISPLAY_NAME = 'Sub-grid Sampling'
    _TEMPLATE_KEY = ''
    _OUTPUT_SUBDIR = ''
    _TCF_COMMAND = r''
    _TCF_COMMENTED_LHS = ''
    _TCF_INSERT_AFTER_LHS = ''
