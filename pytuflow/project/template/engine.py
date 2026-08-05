import re
from string import Template


class TemplateEngine:
    def render(
        self,
        template_text: str,
        variables: dict,
        active_features: list[str] = None,
        feature_configs: dict[str, dict] = None,
    ) -> str:
        """Render a template.

        Parameters
        ----------
        template_text : str
            Raw template content.
        variables : dict
            Variable substitutions (${var} style).
        active_features : list[str], optional
            feature names that are active (used for ##IF feature:X## conditions).
        feature_configs : dict[str, dict], optional
            Mapping of feature name → parsed JSON config dict.  Required for
            ##COMMANDS block_id## directives to be resolved.  If omitted the
            directive is left as a comment in the output.
        """
        if active_features is None:
            active_features = []
        if feature_configs is None:
            feature_configs = {}

        # Build a flat lookup: block_id -> commands list
        block_lookup = _build_block_lookup(feature_configs)

        lines = template_text.splitlines(keepends=True)
        if template_text and not template_text.endswith('\n'):
            lines[-1] = lines[-1] + '\n'

        processed = self._process_directives(lines, variables, active_features, block_lookup)
        result = ''.join(processed)
        return Template(result).safe_substitute(_to_str_vars(variables))

    def _process_directives(self, lines, variables, active_features, block_lookup):
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # ##IF ...## / ##ENDIF##
            m = re.match(r'^##IF\s+(.+?)##\s*$', stripped)
            if m:
                condition = m.group(1).strip()
                block_lines = []
                i += 1
                depth = 1
                while i < len(lines):
                    inner = lines[i].strip()
                    if re.match(r'^##IF\s+', inner):
                        depth += 1
                    elif inner == '##ENDIF##':
                        depth -= 1
                        if depth == 0:
                            break
                    block_lines.append(lines[i])
                    i += 1
                if self._eval_condition(condition, active_features, variables):
                    result.extend(self._process_directives(block_lines, variables, active_features, block_lookup))
                i += 1
                continue

            # ##ITER:${var}## / ##ENDITER##
            # var must resolve to a list of dicts.  Each dict is merged on top of
            # the outer variable scope so outer variables remain accessible.
            m = re.match(r'^##ITER:\$\{(\w+)\}##\s*$', stripped)
            if m:
                var_name = m.group(1).strip()
                block_lines = []
                i += 1
                depth = 1
                while i < len(lines):
                    inner = lines[i].strip()
                    if re.match(r'^##ITER:\$\{', inner):
                        depth += 1
                    elif inner == '##ENDITER##':
                        depth -= 1
                        if depth == 0:
                            break
                    block_lines.append(lines[i])
                    i += 1
                items = variables.get(var_name, [])
                if isinstance(items, str):
                    # Allow a JSON string to be passed from CLI / recipe
                    import json as _json
                    try:
                        items = _json.loads(items)
                    except Exception:
                        items = []
                if not isinstance(items, list):
                    items = [items] if items else []
                for item in items:
                    if not isinstance(item, dict):
                        item = {'item': item}
                    iter_vars = {**variables, **item}
                    expanded = self._process_directives(block_lines, iter_vars, active_features, block_lookup)
                    # Substitute iter-scoped variables immediately — the outer
                    # render() safe_substitute pass only has the top-level vars.
                    str_iter_vars = _to_str_vars(iter_vars)
                    result.extend(
                        Template(ln).safe_substitute(str_iter_vars) for ln in expanded
                    )
                i += 1
                continue

            # ##LOOP var## / ##ENDLOOP##
            m = re.match(r'^##LOOP\s+(.+?)##\s*$', stripped)
            if m:
                var_name = m.group(1).strip()
                block_lines = []
                i += 1
                while i < len(lines):
                    inner = lines[i].strip()
                    if inner == '##ENDLOOP##':
                        break
                    block_lines.append(lines[i])
                    i += 1
                items = variables.get(var_name, [])
                if isinstance(items, str):
                    items = [items]
                for item in items:
                    loop_vars = dict(variables)
                    loop_vars['format'] = item
                    loop_vars['item'] = item
                    expanded = self._process_directives(block_lines, loop_vars, active_features, block_lookup)
                    str_loop_vars = {
                        k: (', '.join(str(x) for x in v) if isinstance(v, list) else str(v))
                        for k, v in loop_vars.items()
                    }
                    result.extend(Template(ln).safe_substitute(str_loop_vars) for ln in expanded)
                i += 1
                continue

            # ##INSERT_POINT label##  — silent no-op; eaten so it never appears in output.
            # (Kept as a recognised directive so custom templates can use it as a
            # logical marker without producing comment noise.)
            m = re.match(r'^##INSERT_POINT\s+(.+?)##\s*$', stripped)
            if m:
                i += 1
                continue

            # ##COMMANDS block_id##
            m = re.match(r'^##COMMANDS\s+(.+?)##\s*$', stripped)
            if m:
                block_id = m.group(1).strip()
                commands = block_lookup.get(block_id, [])
                if commands:
                    str_vars = {
                        k: (', '.join(str(x) for x in v) if isinstance(v, list) else str(v))
                        for k, v in variables.items()
                    }
                    commands = self._process_directives(commands, str_vars, active_features, block_lookup)
                    for cmd in commands:
                        rendered_cmd = Template(cmd).safe_substitute(str_vars)
                        result.append(rendered_cmd + '\n')
                else:
                    # Block ID not found — leave as a comment for visibility
                    result.append(f'! ##COMMANDS {block_id}## (unresolved)\n')
                i += 1
                continue

            result.append(line)
            i += 1
        return result

    def _eval_condition(self, condition: str, active_features: list[str], variables: dict) -> bool:
        negated = False
        if condition.startswith('not:'):
            negated = True
            condition = condition[4:]

        if condition.startswith('feature:'):
            feature_names = condition[8:].split(',')
            result = bool(set(feature_names).intersection(set(active_features)))
        else:
            # ${var}:value — variable equality check (case-insensitive)
            m = re.match(r'^\$\{(\w+)\}(:|==|>|<)(.+)$', condition)
            if m:
                var_name, condition, expected = m.group(1), m.group(2), m.group(3)
                actual = str(variables.get(var_name, ''))
                if condition in [':', '==']:
                    expected = [x.upper() for x in expected.split(';')]
                    result = actual.upper() in expected
                elif condition == '<':
                    result = actual.upper() < expected.upper()
                elif condition == '>':
                    result = actual.upper() > expected.upper()
                else:
                    result = False
            else:
                val = variables.get(condition)
                result = bool(val)

        return (not result) if negated else result


def _build_block_lookup(feature_configs: dict[str, dict]) -> dict[str, list[str]]:
    """Build a flat {block_id: [commands]} dict from all feature configs."""
    lookup: dict[str, list[str]] = {}
    for config in feature_configs.values():
        for block in config.get('command_blocks', []):
            block_id = block.get('id')
            if block_id:
                lookup[block_id] = block.get('commands', [])
    return lookup


def _to_str_vars(variables: dict) -> dict:
    """Flatten all variable values to strings for Template.safe_substitute."""
    return {
        k: (', '.join(str(x) for x in v) if isinstance(v, list) else str(v))
        for k, v in variables.items()
        if not isinstance(v, (dict, list)) or isinstance(v, list)
    }
