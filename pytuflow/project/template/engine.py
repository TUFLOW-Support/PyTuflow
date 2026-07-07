import re
from string import Template


class TemplateEngine:
    def render(self, template_text: str, variables: dict, active_modules: list[str] = None) -> str:
        if active_modules is None:
            active_modules = []
        lines = template_text.splitlines(keepends=True)
        # Ensure trailing newline
        if template_text and not template_text.endswith('\n'):
            lines[-1] = lines[-1] + '\n'
        processed = self._process_directives(lines, variables, active_modules)
        result = ''.join(processed)
        # For substitution, convert list values to strings
        str_vars = {
            k: (', '.join(str(i) for i in v) if isinstance(v, list) else str(v))
            for k, v in variables.items()
        }
        return Template(result).safe_substitute(str_vars)

    def _process_directives(self, lines, variables, active_modules):
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Handle ##IF ...##
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
                # i now points to ##ENDIF##
                if self._eval_condition(condition, active_modules, variables):
                    result.extend(self._process_directives(block_lines, variables, active_modules))
                i += 1
                continue

            # Handle ##LOOP var##
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
                # i now points to ##ENDLOOP##
                items = variables.get(var_name, [])
                if isinstance(items, str):
                    items = [items]
                for item in items:
                    loop_vars = dict(variables)
                    loop_vars['format'] = item
                    loop_vars['item'] = item
                    expanded = self._process_directives(block_lines, loop_vars, active_modules)
                    # Substitute loop-local variables immediately so ${format}/${item} resolve
                    str_loop_vars = {
                        k: (', '.join(str(i) for i in v) if isinstance(v, list) else str(v))
                        for k, v in loop_vars.items()
                    }
                    result.extend(
                        Template(line).safe_substitute(str_loop_vars) for line in expanded
                    )
                i += 1
                continue

            # Handle ##INSERT_POINT label##
            m = re.match(r'^##INSERT_POINT\s+(.+?)##\s*$', stripped)
            if m:
                label = m.group(1).strip()
                result.append(f'! ##INSERT_POINT {label}##\n')
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
            val = variables.get(condition)
            result = bool(val)

        return (not result) if negated else result
