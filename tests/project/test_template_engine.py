"""Tests for the template engine directives and variable substitution."""
import pytest
from pytuflow.project.template.engine import TemplateEngine


@pytest.fixture
def engine():
    return TemplateEngine()


class TestIfDirective:
    def test_if_module_active(self, engine):
        tmpl = "##IF module:estry##\nestry line\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=['estry'])
        assert 'estry line' in result

    def test_if_module_inactive(self, engine):
        tmpl = "##IF module:estry##\nestry line\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert 'estry line' not in result

    def test_if_not_module_active(self, engine):
        """##IF not:module:estry## block should appear when module NOT active."""
        tmpl = "##IF not:module:estry##\nno estry\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert 'no estry' in result

    def test_if_not_module_suppressed(self, engine):
        tmpl = "##IF not:module:estry##\nno estry\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=['estry'])
        assert 'no estry' not in result

    def test_if_variable_truthy(self, engine):
        tmpl = "##IF my_var##\nyes\n##ENDIF##\n"
        result = engine.render(tmpl, {'my_var': '1'}, active_modules=[])
        assert 'yes' in result

    def test_if_variable_falsy(self, engine):
        tmpl = "##IF my_var##\nyes\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert 'yes' not in result

    def test_if_directive_line_not_in_output(self, engine):
        tmpl = "##IF module:estry##\nestry line\n##ENDIF##\n"
        result = engine.render(tmpl, {}, active_modules=['estry'])
        assert '##IF' not in result
        assert '##ENDIF##' not in result


class TestLoopDirective:
    def test_loop_list_values(self, engine):
        tmpl = "##LOOP fmts##\nFormat == ${format}\n##ENDLOOP##\n"
        result = engine.render(tmpl, {'fmts': ['XMDF', 'CSV']}, active_modules=[])
        assert 'Format == XMDF' in result
        assert 'Format == CSV' in result

    def test_loop_single_string(self, engine):
        tmpl = "##LOOP fmts##\n${item}\n##ENDLOOP##\n"
        result = engine.render(tmpl, {'fmts': 'XMDF'}, active_modules=[])
        assert 'XMDF' in result

    def test_loop_empty(self, engine):
        tmpl = "before\n##LOOP fmts##\n${item}\n##ENDLOOP##\nafter\n"
        result = engine.render(tmpl, {'fmts': []}, active_modules=[])
        assert 'before' in result
        assert 'after' in result
        assert '${item}' not in result

    def test_loop_directive_lines_not_in_output(self, engine):
        tmpl = "##LOOP fmts##\n${item}\n##ENDLOOP##\n"
        result = engine.render(tmpl, {'fmts': ['X']}, active_modules=[])
        assert '##LOOP' not in result
        assert '##ENDLOOP##' not in result


class TestInsertPoint:
    def test_insert_point_is_silent_noop(self, engine):
        """##INSERT_POINT## is eaten — produces no output at all."""
        tmpl = "line1\n##INSERT_POINT control_files##\nline3\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert '##INSERT_POINT' not in result
        assert 'line1' in result
        assert 'line3' in result

    def test_insert_point_leaves_no_comment(self, engine):
        tmpl = "##INSERT_POINT my_label##\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert result.strip() == ''


class TestVariableSubstitution:
    def test_simple_substitution(self, engine):
        tmpl = "Model == ${model_name}\n"
        result = engine.render(tmpl, {'model_name': 'test_model'}, active_modules=[])
        assert 'Model == test_model' in result

    def test_missing_variable_kept(self, engine):
        """safe_substitute leaves missing variables as-is."""
        tmpl = "Value == ${missing_var}\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert '${missing_var}' in result

    def test_list_value_joined_for_substitution(self, engine):
        tmpl = "Formats == ${fmts}\n"
        result = engine.render(tmpl, {'fmts': ['XMDF', 'CSV']}, active_modules=[])
        assert 'Formats == XMDF, CSV' in result


class TestMapOutputLoop:
    """Integration test matching the TCF template pattern."""

    def test_map_output_formats_loop(self, engine):
        tmpl = (
            "##LOOP map_output_formats##\n"
            "Map Output Format == ${format}\n"
            "##ENDLOOP##\n"
        )
        result = engine.render(
            tmpl, {'map_output_formats': ['XMDF', 'SHP']}, active_modules=[]
        )
        assert 'Map Output Format == XMDF' in result
        assert 'Map Output Format == SHP' in result


class TestCommandsDirective:
    """Tests for the ##COMMANDS block_id## directive."""

    def _make_config(self, block_id, commands):
        return {
            'command_blocks': [
                {'id': block_id, 'commands': commands}
            ]
        }

    def test_commands_resolved_from_module_config(self, engine):
        tmpl = "##IF module:estry##\n##COMMANDS estry_tcf##\n##ENDIF##\n"
        cfg = self._make_config('estry_tcf', ['Estry Control File == ..\\model\\m.ecf'])
        result = engine.render(tmpl, {}, active_modules=['estry'], module_configs={'estry': cfg})
        assert 'Estry Control File == ..\\model\\m.ecf' in result
        assert '##COMMANDS' not in result

    def test_commands_variable_substitution(self, engine):
        tmpl = "##COMMANDS test_block##\n"
        cfg = self._make_config('test_block', ['Model == ${model_name}'])
        result = engine.render(tmpl, {'model_name': 'mymodel'}, module_configs={'test': cfg})
        assert 'Model == mymodel' in result

    def test_commands_unresolved_becomes_comment(self, engine):
        """Block ID with no matching config emits a visible comment."""
        tmpl = "##COMMANDS unknown_block##\n"
        result = engine.render(tmpl, {}, module_configs={})
        assert '! ##COMMANDS unknown_block## (unresolved)' in result

    def test_commands_not_rendered_when_module_inactive(self, engine):
        tmpl = "##IF module:estry##\n##COMMANDS estry_tcf##\n##ENDIF##\n"
        cfg = self._make_config('estry_tcf', ['Estry Control File == ..\\model\\m.ecf'])
        result = engine.render(tmpl, {}, active_modules=[], module_configs={'estry': cfg})
        assert 'Estry Control File' not in result

    def test_commands_multiple_commands(self, engine):
        tmpl = "##COMMANDS block##\n"
        cfg = self._make_config('block', ['Line1 == a', 'Line2 == b'])
        result = engine.render(tmpl, {}, module_configs={'mod': cfg})
        assert 'Line1 == a' in result
        assert 'Line2 == b' in result

    def test_commands_multiple_modules(self, engine):
        """Block IDs from multiple modules are all resolved."""
        tmpl = "##COMMANDS a_block##\n##COMMANDS b_block##\n"
        configs = {
            'mod_a': self._make_config('a_block', ['A == 1']),
            'mod_b': self._make_config('b_block', ['B == 2']),
        }
        result = engine.render(tmpl, {}, module_configs=configs)
        assert 'A == 1' in result
        assert 'B == 2' in result


class TestSortOrder:
    """Tests that sort_order controls module application order."""

    def test_sort_order_in_module_configs(self):
        """All bundled module JSONs should have a sort_order field."""
        from pytuflow.project.template.manager import TemplateManager
        manager = TemplateManager('hpc')
        from pytuflow.project.hpc.project import get_available_modules
        for name in get_available_modules():
            cfg = manager.get_module_config(name)
            assert 'sort_order' in cfg, f"Module '{name}' missing sort_order"

    def test_get_module_instances_sorted(self):
        """_get_module_instances() returns modules sorted by sort_order."""
        import tempfile, os
        from pytuflow.project import HPCProject
        with tempfile.TemporaryDirectory() as tmp:
            proj = HPCProject(
                name='test',
                output_dir=tmp,
                modules=['po', 'sgs', 'estry'],  # unsorted: po=80, sgs=5, estry=20
            )
            instances = proj._get_module_instances()
            orders = [m._get_config().get('sort_order') for m in instances]
            assert orders == sorted(orders), f"Modules not in sort_order: {orders}"


class TestNormalizeSlashes:
    """Tests for the _normalize_slashes helper in HPCBaseModule."""

    def test_backslash_converted_on_current_os(self):
        import os
        from pytuflow.project.hpc.modules._base import _normalize_slashes
        result = _normalize_slashes('..\\model\\mymodel_001.ecf')
        assert '\\' not in result or os.sep == '\\'
        assert os.sep in result

    def test_forward_slash_converted_on_current_os(self):
        import os
        from pytuflow.project.hpc.modules._base import _normalize_slashes
        result = _normalize_slashes('../model/mymodel_001.ecf')
        assert '/' not in result or os.sep == '/'
        assert os.sep in result

    def test_mixed_slashes_normalized(self):
        import os
        from pytuflow.project.hpc.modules._base import _normalize_slashes
        result = _normalize_slashes('..\\model/mymodel_001.ecf')
        assert result == f'..{os.sep}model{os.sep}mymodel_001.ecf'

    def test_no_slashes_unchanged(self):
        from pytuflow.project.hpc.modules._base import _normalize_slashes
        assert _normalize_slashes('SGS == ON') == 'SGS == ON'

    def test_commands_use_os_sep(self, tmp_path):
        """Integration: commands written to a CF use the OS path separator."""
        import os
        from pytuflow.project.hpc.modules.estry import EstryModule
        from pytuflow import TCF

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        tcf_path.write_text('Read Materials File == ..\\model\\mymodel_mat.csv\n', encoding='utf-8')

        tcf = TCF(tcf_path)
        EstryModule().apply_to_control_files({'tcf': tcf}, {'model_name': 'mymodel', 'iter': '001'})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        ecf_line = next(l for l in content.splitlines() if 'estry control file' in l.lower())
        assert os.sep in ecf_line, f"Expected {os.sep!r} in: {ecf_line}"
        wrong_sep = '/' if os.sep == '\\' else '\\'
        assert wrong_sep not in ecf_line, f"Unexpected {wrong_sep!r} in: {ecf_line}"
