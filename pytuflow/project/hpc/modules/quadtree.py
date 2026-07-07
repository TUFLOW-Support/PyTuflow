from ._base import HPCBaseModule


class QuadtreeModule(HPCBaseModule):
    NAME = 'quadtree'
    DISPLAY_NAME = 'Quadtree (Variable Resolution)'
    _TEMPLATE_KEY = 'model/${model_name}_${iter}.qcf'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'Quadtree Control File == ..\model\${model_name}_${iter}.qcf'
    _TCF_COMMENTED_LHS = 'quadtree control file'
    _TCF_INSERT_AFTER_LHS = 'Geometry Control File'
