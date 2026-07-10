import re
from string import Template


class TemplateEngine:
    def render(
        self,
        template_text: str,
        variables: dict,
        active_modules: list[str] = None,
        module_configs: dict[str, dict] = None,
    ) -> str:
        """Render a template.

        Parameters
        ----------
        template_text : str
            Raw template content.
        variables : dict
            Variable substitutions (${var} style).
        active_modules : list[str], optional
            Module names that are active (used for ##IF module:X## conditions).
        module_configs : dict[str, dict], optional
            Mapping of module name → parsed JSON config dict.  Required for
            ##COMMANDS block_id## directives to be resolved.  If omitted the
            directive is left as a comment in the output.
        """
        if active_modules is None:
            active_modules = []
        if module_configs is None:
            module_configs = {}

        # Build a flat lookup: block_id -> commands list
        block_lookup = _build_block_lookup(module_configs)

        lines = template_text.splitlines(keepends=True)
        if template_text and not template_text.endswith('\n'):
            lines[-1] = lines[-1] + '\n'

        processed = self._process_directives(lines, variables, active_modules, block_lookup)
        result = ''.join(processed)

        str_vars = {
            k: (', '.join(str(i) for i in v) if isinstance(v, list) else str(v))
            for k, v in variables.items()
        }
        return Template(result).safe_substitute(str_vars)

    def _process_directives(self, lines, variables, active_modules, block_lookup):
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
                if self._eval_condition(condition, active_modules, variables):
                    result.extend(self._process_directives(block_lines, variables, active_modules, block_lookup))
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
                    expanded = self._process_directives(block_lines, loop_vars, active_modules, block_lookup)
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

    def _eval_condition(self, condition: str, active_modules: list[str], variables: dict) -> bool:
        negated = False
        if condition.startswith('not:'):
            negated = True
            condition = condition[4:]

        if condition.startswith('module:'):
            module_name = condition[7:]
            result = module_name in active_modules
        else:
            # ${var}:value — variable equality check (case-insensitive)
            m = re.match(r'^\$\{(\w+)\}:(.+)$', condition)
            if m:
                var_name, expected = m.group(1), m.group(2)
                actual = str(variables.get(var_name, ''))
                result = actual.upper() == expected.upper()
            else:
                val = variables.get(condition)
                result = bool(val)

        return (not result) if negated else result


def _build_block_lookup(module_configs: dict[str, dict]) -> dict[str, list[str]]:
    """Build a flat {block_id: [commands]} dict from all module configs."""
    lookup: dict[str, list[str]] = {}
    for config in module_configs.values():
        for block in config.get('command_blocks', []):
            block_id = block.get('id')
            if block_id:
                lookup[block_id] = block.get('commands', [])
    return lookup
