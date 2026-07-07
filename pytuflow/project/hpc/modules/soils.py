from string import Template

from ._base import HPCBaseModule


class SoilsModule(HPCBaseModule):
    NAME = 'soils'
    DISPLAY_NAME = 'Soils (Infiltration)'
    _TEMPLATE_KEY = 'model/${model_name}_soils.tsoilf'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'Read Soils File == ..\model\${model_name}_soils.tsoilf'
    _TCF_COMMENTED_LHS = 'read soils file'
    _TCF_INSERT_AFTER_LHS = 'Read Materials File'

    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        template_key = self._TEMPLATE_KEY
        filename = Template(template_key.split('/')[-1]).safe_substitute(variables)
        output_rel = f'{self._OUTPUT_SUBDIR}/{filename}'
        return [(template_key, output_rel)]
