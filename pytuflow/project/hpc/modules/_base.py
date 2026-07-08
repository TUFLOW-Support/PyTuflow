from __future__ import annotations

from string import Template

from ...abc.module import BaseModule
from ...template.manager import TemplateManager


class HPCBaseModule(BaseModule):
    """Shared base for all HPC modules. Command configuration is driven by a JSON file
    cached at ``~/.tuflow_model_files/project_templates/modules/hpc/<name>.json``."""

    NAME: str = ''
    DISPLAY_NAME: str = ''

    def _get_config(self) -> dict:
        """Load this module's JSON config via the TemplateManager (reads from cache)."""
        manager = TemplateManager('hpc')
        return manager.get_module_config(self.NAME)

    # ------------------------------------------------------------------
    # BaseModule interface
    # ------------------------------------------------------------------

    def get_template_files(self, variables: dict) -> list[tuple[str, str]]:
        config = self._get_config()
        result = []
        for tf in config.get('template_files', []):
            template_key = tf['template_key']
            subdir = tf.get('output_subdir', 'model')
            filename = Template(template_key.split('/')[-1]).safe_substitute(variables)
            output_rel = f'{subdir}/{filename}'
            result.append((template_key, output_rel))
        return result

    def apply_to_control_files(self, control_files: dict, variables: dict) -> None:
        """Apply this module's command blocks to the supplied control file objects.

        Parameters
        ----------
        control_files : dict[str, ControlFile]
            Mapping of CF type key (e.g. ``'tcf'``, ``'tgc'``) to the loaded
            control file build-state object.
        variables : dict
            Template variable substitutions (model_name, iter, …).
        """
        config = self._get_config()
        for block in config.get('command_blocks', []):
            target = block.get('target_cf', 'tcf')
            cf = control_files.get(target)
            if cf is None:
                continue
            self._apply_block(cf, block, variables)

    # Legacy shim so any code that still calls apply_to_tcf keeps working.
    def apply_to_tcf(self, tcf, variables: dict) -> None:
        self.apply_to_control_files({'tcf': tcf}, variables)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_block(self, cf, block: dict, variables: dict) -> None:
        """Apply a single command block to a control file."""
        raw_commands: list[str] = block.get('commands', [])
        if not raw_commands:
            return

        # Substitute template variables in each command.
        commands = [Template(cmd).safe_substitute(variables) for cmd in raw_commands]

        # Find the first non-comment command (used for existence checks).
        first_active = next((c for c in commands if not c.strip().startswith('!')), None)
        if first_active is None:
            return

        first_lhs = first_active.split('==')[0].strip().lower()

        # 1. Already exists (uncommented) — skip the whole block.
        if cf.find_input(lhs=first_lhs, recursive=False):
            return

        # 2. Placement rule — insert after the last command in the named section.
        placement_rule = block.get('placement_rule')
        if placement_rule:
            rules = TemplateManager.get_rules()
            rule = rules.get(placement_rule, {})
            rule_lhs = [lhs.lower() for lhs in rule.get('commands', [])]
            if rule_lhs:
                last_ref = None
                for lhs in rule_lhs:
                    matches = cf.find_input(lhs=lhs, recursive=False)
                    if matches:
                        last_ref = matches[-1]
                if last_ref is not None:
                    self._insert_block_after(cf, last_ref, commands)
                    return

        # 3. A commented-out version of the first active command exists — uncomment it.
        commented_lhs = block.get('commented_lhs')
        if commented_lhs:
            commented = cf.find_input(filter_by=commented_lhs, comments=True, recursive=False)
            if commented:
                cf.uncomment(commented[0])
                return

        # 4. Insert the block after a reference command.
        insert_after_lhs = block.get('insert_after_lhs')
        if insert_after_lhs:
            refs = cf.find_input(lhs=insert_after_lhs, recursive=False)
            if refs:
                self._insert_block_after(cf, refs[-1], commands)
                return

        # 5. Fallback — append the whole block to the end of the file.
        for cmd in commands:
            if cmd.strip():
                cf.append_input(cmd)

    @staticmethod
    def _insert_block_after(cf, ref_inp, commands: list[str]) -> None:
        """Insert *commands* into *cf* sequentially after *ref_inp*."""
        current_ref = ref_inp
        for cmd in commands:
            if cmd.strip():
                current_ref = cf.insert_input(current_ref, cmd, after=True)
