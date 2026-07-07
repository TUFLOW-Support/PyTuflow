from ._base import HPCBaseModule


class ADModule(HPCBaseModule):
    NAME = 'ad'
    DISPLAY_NAME = 'AD (Advection-Diffusion)'
    _TEMPLATE_KEY = 'model/${model_name}_${iter}.adcf'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'AD Control File == ..\model\${model_name}_${iter}.adcf'
    _TCF_COMMENTED_LHS = 'ad control file'
    _TCF_INSERT_AFTER_LHS = 'BC Control File'
