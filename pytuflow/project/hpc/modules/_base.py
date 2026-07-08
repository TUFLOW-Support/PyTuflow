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
        """Apply a single command block to a control file, checking each command
        individually.

        For each non-comment command:

        * Already exists (uncommented) → skip; advance cursor to its position.
        * Commented version found → uncomment; advance cursor.
        * Neither → insert after cursor; advance cursor.

        Comment / blank lines before the first real command are buffered as
        *decorators* and flushed only if the following real command needs
        inserting — so section headers are not duplicated when all commands
        already exist.

        Comment / blank lines that appear *after* a real command have already
        been processed and are inserted immediately (e.g. placeholder lines
        like ``! Read GIS PO == <path>`` that follow a real command).
        """
        raw_commands: list[str] = block.get('commands', [])
        if not raw_commands:
            return

        commands = [Template(cmd).safe_substitute(variables) for cmd in raw_commands]

        # Verify there is at least one real command worth processing.
        if not any(c.strip() and not c.strip().startswith('!') for c in commands):
            return

        # Find the initial insertion anchor for this block.
        current_ref = self._find_block_anchor(cf, block)

        # Before the first real command, comments are decorators (section headers
        # etc.) — only inserted when a real command needs inserting.
        # After a real command has been processed, comments are trailing content
        # and are inserted immediately after the cursor.
        pending_decorators: list[str] = []
        past_first_real_command = False

        for cmd in commands:
            stripped = cmd.strip()

            if not stripped or stripped.startswith('!'):
                if past_first_real_command:
                    # Trailing comment — insert immediately after cursor.
                    current_ref = self._insert_or_append(cf, current_ref, cmd)
                else:
                    # Pre-command decorator — buffer until we know if real cmd needs inserting.
                    pending_decorators.append(cmd)
                continue

            past_first_real_command = True
            lhs = stripped.split('==')[0].strip()

            # Already exists uncommented — skip; advance cursor to keep order.
            existing = cf.find_input(lhs=lhs, recursive=False)
            if existing:
                pending_decorators.clear()
                current_ref = existing[0]
                continue

            # Auto-detect a commented version: ^\s*!\s*<lhs>\s*== (case-insensitive).
            escaped_lhs = re.escape(lhs)
            auto_pattern = rf'^\s*!\s*{escaped_lhs}\s*=='
            commented = cf.find_input(
                filter_by=auto_pattern,
                comments=True,
                recursive=False,
                regex=True,
                regex_flags=re.IGNORECASE,
            )
            if commented:
                cf.uncomment(commented[0])
                pending_decorators.clear()
                current_ref = commented[0]
                continue

            # Command needs inserting — flush buffered decorators first.
            for dec in pending_decorators:
                if dec.strip():
                    current_ref = self._insert_or_append(cf, current_ref, dec)
            pending_decorators.clear()

            current_ref = self._insert_or_append(cf, current_ref, cmd)

    def _find_block_anchor(self, cf, block: dict):
        """Return the input after which to start inserting, or ``None`` (append mode).

        Priority:
        1. Placement rule (scans CF for last matching command in the rule's list).
        2. ``insert_after_lhs`` fallback.
        3. ``None`` — commands are appended to the end of the file.
        """
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
            last_ref = None
            for cmd_entry in rule.get('commands', []):
                pattern, is_regex, flags = _parse_filter(cmd_entry)
                matches = cf.find_input(
                    lhs=pattern, recursive=False, regex=is_regex, regex_flags=flags
                )
                if matches:
                    last_ref = matches[-1]
            if last_ref is not None:
                return last_ref

        insert_after_lhs = block.get('insert_after_lhs')
        if insert_after_lhs:
            refs = cf.find_input(lhs=insert_after_lhs, recursive=False)
            if refs:
                return refs[-1]

        return None  # append mode

    @staticmethod
    def _insert_or_append(cf, ref_inp, cmd: str):
        """Insert *cmd* after *ref_inp*, or append when *ref_inp* is ``None``."""
        if ref_inp is None:
            cf.append_input(cmd)
            return None  # can't track position after a bare append
        return cf.insert_input(ref_inp, cmd, after=True)
