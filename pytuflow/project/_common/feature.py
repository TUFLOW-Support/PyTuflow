from __future__ import annotations

import re
import typing
from string import Template

from ..abc.feature import BaseFeature
from ..template.manager import TemplateManager
from .utils import _normalize_slashes, _parse_filter

if typing.TYPE_CHECKING:
    from ..._tmf.abc.input import Input


class BaseEngineFeature(BaseFeature):
    """Shared base for all engine features (HPC, FV, …).

    Command configuration is driven by a JSON file cached at
    ``~/.tuflow_model_files/project_templates/features/<engine>/<name>.json``.
    Subclasses must set ``ENGINE_TYPE`` (e.g. ``'hpc'`` or ``'fv'``).
    """

    ENGINE_TYPE: str = ''
    NAME: str = ''
    DISPLAY_NAME: str = ''

    def _get_config(self) -> dict:
        """Load this feature's JSON config via the TemplateManager (reads from cache)."""
        manager = TemplateManager(self.ENGINE_TYPE)
        return manager.get_feature_config(self.NAME)

    def _get_rules(self) -> dict:
        """Load the feature's rules config."""
        manager = TemplateManager(self.ENGINE_TYPE)
        return manager.get_rules()

    # ------------------------------------------------------------------
    # BaseFeature interface
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
        """Apply this feature's command blocks to the supplied control file objects."""
        last_input = None
        config = self._get_config()
        for block in config.get('command_blocks', []):
            target = block.get('target_cf', 'tcf' if self.ENGINE_TYPE == 'hpc' else 'fvc')
            cf = control_files.get(target)
            if cf is None:
                continue
            subtarget = block.get("subtarget_cf") or block.get("target_previous_block")
            if subtarget:
                if block.get("subtarget_cf"):
                    pattern, is_regex, flags = _parse_filter(subtarget)
                    if '==' in pattern:
                        input_subtarget = cf.find_input(filter_by=pattern, regex=is_regex, regex_flags=flags)
                    else:
                        input_subtarget = cf.find_input(lhs=pattern, regex=is_regex, regex_flags=flags)
                else:
                    input_subtarget = [last_input] if last_input else []
                for inp in input_subtarget:
                    if inp.cf:
                        cf = inp.cf[0]
                        break
            last_input = self._apply_block(cf, block, variables)

    def apply_to_tcf(self, tcf, variables: dict) -> None:
        """Legacy shim — delegates to apply_to_control_files."""
        self.apply_to_control_files({'tcf': tcf}, variables)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_block(self, cf, block: dict, variables: dict) -> Input | None:
        """Apply a single command block to a control file.

        Supports two modes:

        **Atomic mode** (``existence_check`` configured): the sentinel is
        checked once; if found the entire block is skipped; if absent all
        commands are inserted unconditionally.

        **Per-command mode** (no ``existence_check``): each command is
        checked individually — skip if uncommented exists, uncomment if
        commented version found, otherwise insert.  Pre-command comments
        are buffered as *decorators* and only flushed when a real command
        needs inserting.

        Returns the last inserted input.
        """
        raw_commands: list[str] = block.get('commands', [])
        if not raw_commands:
            return

        commands = [
            _normalize_slashes(Template(cmd).safe_substitute(variables))
            for cmd in raw_commands
        ]

        # if not any(c.strip() and not c.strip().startswith('!') for c in commands):
        #     return

        # ── Atomic block mode (existence_check configured) ───────────────────
        existence_check = block.get('existence_check')
        if existence_check is not None and not block.get('allow_multiple'):
            is_comment = existence_check.strip().startswith('!')
            pattern, is_regex, flags = _parse_filter(existence_check)
            if is_comment:
                found = cf.find_input(filter_by=pattern, recursive='similar', comments=True, regex=is_regex, regex_flags=flags)
            else:
                if '==' in pattern:
                    found = cf.find_input(filter_by=pattern, recursive='similar', regex=is_regex, regex_flags=flags)
                else:
                    found = cf.find_input(lhs=pattern, recursive='similar', regex=is_regex, regex_flags=flags)
            if found:
                return  # sentinel present — block already inserted

            current_ref, anchor_rule = self._find_block_anchor(cf, block)
            if current_ref:
                cf = current_ref.parent
            for cmd in commands:
                if cmd.strip():
                    current_ref = self._insert_or_append(cf, current_ref, cmd, anchor_rule)
                anchor_rule = 'after'  # switch back to after so that subsequent commands appear in expected order
            return

        # ── Per-command mode (no existence_check) ────────────────────────────
        allow_multiple = block.get('allow_multiple', False)
        current_ref, anchor_rule = self._find_block_anchor(cf, block)
        pending_decorators: list[str] = []
        past_first_real_command = False

        for cmd in commands:
            stripped = cmd.strip()

            if not stripped or (stripped.startswith('!') and not past_first_real_command):
                pending_decorators.append(cmd)
                continue

            past_first_real_command = True
            lhs = stripped.split('==')[0].strip()

            if stripped.startswith('!'):
                existing = cf.find_input(stripped, comments=True)
            else:
                existing = cf.find_input(lhs=lhs, recursive=False)
            if existing and not allow_multiple:
                pending_decorators.clear()
                current_ref = existing[0]
                continue

            if not allow_multiple:
                escaped_lhs = re.escape(lhs)
                auto_pattern = rf'^\s*!\s*{escaped_lhs}\s*=='
                commented = cf.find_input(
                    filter_by=auto_pattern,
                    comments=True,
                    recursive='similar',
                    regex=True,
                    regex_flags=re.IGNORECASE,
                )
                if commented:
                    cf.uncomment(commented[0])
                    pending_decorators.clear()
                    current_ref = commented[0]
                    continue

            if current_ref:
                cf = current_ref.parent

            for dec in pending_decorators:
                if dec.strip():
                    current_ref = self._insert_or_append(cf, current_ref, dec, anchor_rule)
                anchor_rule = 'after'  # switch back to after so that subsequent commands appear in expected order
            pending_decorators.clear()

            current_ref = self._insert_or_append(cf, current_ref, cmd, anchor_rule)

        return current_ref

    def _find_block_anchor(self, cf, block: dict) -> tuple['Input | None', str]:
        """Return the input after which to start inserting, or ``None`` (append).

        Priority:
        1. Placement rule (last matching command in the rule's command list).
        2. ``insert_after_lhs`` fallback.
        3. ``None`` — commands are appended to the end of the file.
        """
        rule_type = ''
        placement_rule = block.get('placement_rule')
        if placement_rule:
            rules = self._get_rules()
            rule = rules.get(placement_rule, {})
            rule_type = rule.get('rule', 'after')
            if rule_type not in ['before', 'after']:
                raise NotImplementedError(
                    f"Placement rule strategy '{rule_type}' (from rule '{placement_rule}') "
                    f"is not implemented."
                )
            last_ref = None
            for cmd_entry in rule.get('commands', []):
                pattern, is_regex, flags = _parse_filter(cmd_entry)
                if pattern.lstrip() and pattern.lstrip()[0] == '!' or pattern.lstrip()[0] == '#':
                    matches = cf.find_input(
                        filter_by=pattern, recursive='similar', regex=is_regex, regex_flags=flags, comments=True
                    )
                elif '==' in pattern:
                    matches = cf.find_input(
                        filter_by=pattern, recursive='similar', regex=is_regex, regex_flags=flags
                    )
                else:
                    matches = cf.find_input(
                        lhs=pattern, recursive='similar', regex=is_regex, regex_flags=flags
                    )
                if matches:
                    last_ref = matches[-1]
            if last_ref is not None:
                return last_ref, rule_type

        insert_after_lhs = block.get('insert_after_lhs')
        if insert_after_lhs:
            refs = cf.find_input(lhs=insert_after_lhs, recursive='similar')
            if refs:
                return refs[-1], rule_type

        return None, rule_type  # append mode

    @staticmethod
    def _insert_or_append(cf, ref_inp, cmd: str, anchor_rule: str):
        """Insert *cmd* after *ref_inp*, or append when *ref_inp* is ``None``."""
        if ref_inp is None:
            return cf.append_input(cmd)
        return cf.insert_input(ref_inp, cmd, after=False if anchor_rule == 'before' else True, gap=1 if anchor_rule == 'before' else 0)
