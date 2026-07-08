from __future__ import annotations

import re
from string import Template

from ...abc.module import BaseModule
from ...template.manager import TemplateManager


def _parse_filter(value: str) -> tuple[str, bool, int]:
    """Parse a filter string that may use ``/pattern/flags`` regex syntax.

    Returns ``(pattern, is_regex, flags)``.  Supported flag characters:
    ``i`` (IGNORECASE), ``m`` (MULTILINE), ``s`` (DOTALL).

    Plain strings are returned unchanged with ``is_regex=False, flags=0``.

    Examples
    --------
    >>> _parse_filter("set soil")
    ('set soil', False, 0)
    >>> _parse_filter("/^set soil\\\\s*==/i")
    ('^set soil\\\\s*==', True, re.IGNORECASE)
    """
    if value.startswith('/'):
        last_slash = value.rfind('/', 1)
        if last_slash > 0:
            pattern = value[1:last_slash]
            flag_chars = value[last_slash + 1:]
            flags = 0
            for char, flag in (('i', re.IGNORECASE), ('m', re.MULTILINE), ('s', re.DOTALL)):
                if char in flag_chars:
                    flags |= flag
            return pattern, True, flags
    return value, False, 0


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

        # 2. Placement rule — insert using the strategy specified by rule["rule"].
        placement_rule = block.get('placement_rule')
        if placement_rule:
            rules = TemplateManager.get_rules()
            rule = rules.get(placement_rule, {})
            rule_type = rule.get('rule', 'after')
            if rule_type != 'after':
                raise NotImplementedError(
                    f"Placement rule strategy '{rule_type}' (from rule '{placement_rule}') "
                    f"is not implemented. Only 'after' is currently supported."
                )
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
            pattern, is_regex, flags = _parse_filter(commented_lhs)
            commented = cf.find_input(
                filter_by=pattern,
                comments=True,
                recursive=False,
                regex=is_regex,
                regex_flags=flags,
            )
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
