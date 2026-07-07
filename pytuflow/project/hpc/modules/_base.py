from __future__ import annotations

from string import Template

from ...abc.module import BaseModule


class HPCBaseModule(BaseModule):
    """Shared base for all HPC modules."""

    NAME: str = ''
    DISPLAY_NAME: str = ''
    _TEMPLATE_KEY: str = ''        # e.g. 'model/${model_name}_${iter}.ecf'
    _OUTPUT_SUBDIR: str = 'model'  # subdirectory within project
    _TCF_COMMAND: str = ''         # full command line to add
    _TCF_COMMENTED_LHS: str = ''   # lowercase lhs to search for commented-out version
    _TCF_INSERT_AFTER_LHS: str = '' # fallback: insert after this lhs

    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        if not self._TEMPLATE_KEY:
            return []
        template_key = self._TEMPLATE_KEY
        filename = Template(self._TEMPLATE_KEY.split('/')[-1]).safe_substitute(variables)
        output_rel = f'{self._OUTPUT_SUBDIR}/{filename}'
        return [(template_key, output_rel)]

    def apply_to_tcf(self, tcf, variables: dict) -> None:
        command = Template(self._TCF_COMMAND).safe_substitute(variables)
        lhs = command.split('==')[0].strip().lower()

        # 1. Check if command already exists (not commented)
        existing = tcf.find_input(lhs=lhs, recursive=False)
        if existing:
            return  # already present, skip

        # 2. Find ##INSERT_POINT control_files## comment
        insert_point = tcf.find_input(
            filter_by='##INSERT_POINT control_files##', comments=True, recursive=False
        )
        if insert_point:
            tcf.insert_input(insert_point[0], command, after=True)
            return

        # 3. Find commented-out version and uncomment it
        if self._TCF_COMMENTED_LHS:
            commented = tcf.find_input(
                filter_by=self._TCF_COMMENTED_LHS, comments=True, recursive=False
            )
            if commented:
                tcf.uncomment(commented[0])
                return

        # 4. Find _TCF_INSERT_AFTER_LHS and insert after it
        if self._TCF_INSERT_AFTER_LHS:
            ref = tcf.find_input(lhs=self._TCF_INSERT_AFTER_LHS, recursive=False)
            if ref:
                tcf.insert_input(ref[-1], command, after=True)
                return

        # 5. Append to TCF
        tcf.append_input(command)
