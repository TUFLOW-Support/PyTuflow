from ._base import HPCBaseModule


class RFModule(HPCBaseModule):
    NAME = 'rf'
    DISPLAY_NAME = 'RF (Rainfall)'
    _TEMPLATE_KEY = 'model/${model_name}_${iter}.rf'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'Read Rainfall File == ..\model\${model_name}_${iter}.rf'
    _TCF_COMMENTED_LHS = 'read rainfall file'
    _TCF_INSERT_AFTER_LHS = 'Read Materials File'
