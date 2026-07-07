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
    def test_insert_point_becomes_comment(self, engine):
        tmpl = "line1\n##INSERT_POINT control_files##\nline3\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert '! ##INSERT_POINT control_files##' in result
        assert 'line1' in result
        assert 'line3' in result

    def test_insert_point_original_removed(self, engine):
        tmpl = "##INSERT_POINT my_label##\n"
        result = engine.render(tmpl, {}, active_modules=[])
        assert result.strip() == '! ##INSERT_POINT my_label##'


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
