from ._base import HPCBaseModule


class EstryModule(HPCBaseModule):
    NAME = 'estry'
    DISPLAY_NAME = 'Estry (1D Drainage)'
    _TEMPLATE_KEY = 'model/${model_name}_${iter}.ecf'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'Estry Control File == ..\model\${model_name}_${iter}.ecf'
    _TCF_COMMENTED_LHS = 'estry control file'
    _TCF_INSERT_AFTER_LHS = 'BC Control File'
