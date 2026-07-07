from string import Template

from ._base import HPCBaseModule


class EventsModule(HPCBaseModule):
    NAME = 'events'
    DISPLAY_NAME = 'Events (Scenario/Event File)'
    _TEMPLATE_KEY = 'model/${model_name}_events.tef'
    _OUTPUT_SUBDIR = 'model'
    _TCF_COMMAND = r'Event File == ..\model\${model_name}_events.tef'
    _TCF_COMMENTED_LHS = 'event file'
    _TCF_INSERT_AFTER_LHS = 'SGS Sample Target Distance'

    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        template_key = self._TEMPLATE_KEY
        filename = Template(template_key.split('/')[-1]).safe_substitute(variables)
        output_rel = f'{self._OUTPUT_SUBDIR}/{filename}'
        return [(template_key, output_rel)]
