"""Tests for HPCProject create and insert_module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pytuflow.project.hpc.project import HPCProject, get_available_modules, _variables_from_tcf_path
from pytuflow.project.template.manager import TemplateManager


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'my_project'


@pytest.fixture
def basic_project(project_dir):
    return HPCProject(
        name='mymodel',
        output_dir=project_dir,
        iter='001',
        gis_format='SHP',
        map_output_formats=['XMDF'],
    )


class TestHPCProjectValidation:
    def test_valid_project_no_errors(self, basic_project):
        assert basic_project.validate() == []

    def test_empty_name_raises(self, project_dir):
        p = HPCProject(name='', output_dir=project_dir)
        errors = p.validate()
        assert any('name' in e for e in errors)


class TestHPCProjectCreate:
    def test_create_returns_output_dir(self, basic_project, project_dir):
        result = basic_project.create()
        assert result == project_dir

    def test_standard_directories_created(self, basic_project, project_dir):
        basic_project.create()
        for d in ['runs', 'model', 'bc_dbase', 'results', 'check', 'log']:
            assert (project_dir / d).is_dir(), f"Missing directory: {d}"

    def test_tcf_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'runs' / 'mymodel_001.tcf').exists()

    def test_tgc_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'model' / 'mymodel_001.tgc').exists()

    def test_tbc_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'model' / 'mymodel_001.tbc').exists()

    def test_mat_csv_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'model' / 'mymodel_mat.csv').exists()

    def test_bc_dbase_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'bc_dbase' / 'bc_dbase.csv').exists()

    def test_tcf_contains_model_name(self, basic_project, project_dir):
        basic_project.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'mymodel' in tcf_text

    def test_tcf_contains_gis_format(self, basic_project, project_dir):
        basic_project.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'GIS Format == SHP' in tcf_text

    def test_tcf_map_output_format(self, basic_project, project_dir):
        basic_project.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Map Output Format == XMDF' in tcf_text

    def test_tcf_multiple_map_output_formats(self, project_dir):
        p = HPCProject('mymodel', project_dir, map_output_formats=['XMDF', 'SHP'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Map Output Format == XMDF' in tcf_text
        assert 'Map Output Format == SHP' in tcf_text

    def test_tcf_directive_lines_removed(self, basic_project, project_dir):
        basic_project.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert '##IF' not in tcf_text
        assert '##ENDIF##' not in tcf_text
        assert '##LOOP' not in tcf_text
        assert '##ENDLOOP##' not in tcf_text

    def test_validation_error_raises(self, project_dir):
        p = HPCProject(name='', output_dir=project_dir)
        with pytest.raises(ValueError):
            p.create()


class TestHPCProjectWithEstryModule:
    def test_ecf_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['estry'])
        p.create()
        assert (project_dir / 'model' / 'mymodel_001.ecf').exists()

    def test_tcf_contains_estry_command(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['estry'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Estry Control File' in tcf_text
        # Should be uncommented (active module)
        lines = [l for l in tcf_text.splitlines() if 'Estry Control File' in l]
        assert any(not l.strip().startswith('!') for l in lines)

    def test_tcf_no_estry_commented(self, project_dir):
        """Without estry module, estry line should be commented."""
        p = HPCProject('mymodel', project_dir, modules=[])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Estry Control File' in l]
        assert lines, "Estry Control File line should exist (commented)"
        assert all(l.strip().startswith('!') for l in lines)


class TestHPCProjectWithSoilsModule:
    def test_soils_file_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['soils'])
        p.create()
        assert (project_dir / 'model' / 'mymodel_soils.tsoilf').exists()

    def test_tcf_contains_soils_command(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['soils'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Read Soils File' in l]
        assert any(not l.strip().startswith('!') for l in lines)


class TestHPCProjectWithEventsModule:
    def test_tef_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['events'])
        p.create()
        assert (project_dir / 'model' / 'mymodel_events.tef').exists()

    def test_tcf_events_uncommented_when_active(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['events'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Event File' in l]
        assert any(not l.strip().startswith('!') for l in lines)

    def test_tcf_events_commented_when_inactive(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=[])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Event File' in l]
        assert lines
        assert all(l.strip().startswith('!') for l in lines)


class TestHPCProjectInsertPoint:
    def test_insert_point_in_tcf(self, project_dir):
        p = HPCProject('mymodel', project_dir)
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert '! ##INSERT_POINT control_files##' in tcf_text


class TestHPCProjectUnknownModule:
    def test_unknown_module_raises(self, project_dir):
        p = HPCProject('mymodel', project_dir, modules=['nonexistent'])
        with pytest.raises(ValueError, match="Unknown module"):
            p.create()


class TestGetAvailableModules:
    def test_returns_all_modules(self):
        modules = get_available_modules()
        expected = {'estry', 'quadtree', 'soils', 'ad', 'toc', 'rf', 'events'}
        assert set(modules.keys()) == expected

    def test_modules_have_name(self):
        modules = get_available_modules()
        for name, cls in modules.items():
            assert cls.NAME == name

    def test_modules_have_display_name(self):
        modules = get_available_modules()
        for name, cls in modules.items():
            assert cls.DISPLAY_NAME


class TestVariablesFromTcfPath:
    def test_parses_model_name_and_iter(self, tmp_path):
        tcf = tmp_path / 'runs' / 'mymodel_001.tcf'
        v = _variables_from_tcf_path(tcf)
        assert v['model_name'] == 'mymodel'
        assert v['iter'] == '001'

    def test_no_iter_in_name(self, tmp_path):
        tcf = tmp_path / 'runs' / 'mymodel.tcf'
        v = _variables_from_tcf_path(tcf)
        assert v['model_name'] == 'mymodel'
        assert v['iter'] == '001'

    def test_overrides_applied(self, tmp_path):
        tcf = tmp_path / 'runs' / 'mymodel_001.tcf'
        v = _variables_from_tcf_path(tcf, model_name='override')
        assert v['model_name'] == 'override'


class TestHPCBaseModuleApplyToTcf:
    """Tests for HPCBaseModule.apply_to_tcf logic."""

    def test_apply_skips_if_already_present(self, project_dir):
        """If command already exists in TCF, apply_to_tcf should skip."""
        from pytuflow.project.hpc.modules.estry import EstryModule
        from pytuflow import TCF

        # Create project with estry already
        p = HPCProject('mymodel', project_dir, modules=['estry'])
        p.create()

        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'
        tcf = TCF(tcf_path)
        before_lines = list(tcf.find_input(lhs='estry control file', recursive=False))

        # Apply again - should be a no-op
        module = EstryModule()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        module.apply_to_tcf(tcf, variables)

        after_lines = list(tcf.find_input(lhs='estry control file', recursive=False))
        assert len(before_lines) == len(after_lines)

    def test_apply_uncomments_existing_comment(self, project_dir):
        """apply_to_tcf should uncomment an existing commented line."""
        from pytuflow.project.hpc.modules.estry import EstryModule
        from pytuflow import TCF

        # Create project WITHOUT estry (so estry line is commented)
        p = HPCProject('mymodel', project_dir, modules=[])
        p.create()

        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'
        tcf = TCF(tcf_path)

        # Verify the estry line is commented
        commented = tcf.find_input(filter_by='estry control file', comments=True, recursive=False)
        assert commented, "Estry line should be commented"

        # Now apply the estry module
        module = EstryModule()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        module.apply_to_tcf(tcf, variables)
        tcf.write('inplace')

        # Re-read and verify it's now uncommented
        tcf2 = TCF(tcf_path)
        active = tcf2.find_input(lhs='estry control file', recursive=False)
        assert active, "Estry Control File should now be active"


class TestTemplateManagerIntegration:
    def test_list_templates_includes_tcf(self):
        manager = TemplateManager('hpc')
        templates = manager.list_templates()
        assert any('tcf' in t for t in templates)

    def test_get_template_returns_content(self):
        manager = TemplateManager('hpc')
        content = manager.get_template('runs/${model_name}_${iter}.tcf')
        assert 'GIS Format' in content

    def test_init_cache_creates_dir(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        manager.init_cache()
        assert manager._cache_dir.exists()

    def test_reset_cache_recreates(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        manager.init_cache()
        # Modify a file
        test_file = manager._cache_dir / 'runs' / '${model_name}_${iter}.tcf'
        original = test_file.read_text()
        test_file.write_text('modified')
        assert test_file.read_text() == 'modified'
        # Reset
        manager.reset_cache()
        assert test_file.read_text() == original


class TestCLICommands:
    """Integration tests for the CLI entry points."""

    def test_list_modules(self, capsys):
        import sys
        from pytuflow.project.__main__ import cmd_list_modules
        cmd_list_modules(None)
        captured = capsys.readouterr()
        assert 'estry' in captured.out

    def test_create_via_main(self, tmp_path):
        import subprocess, sys
        result = subprocess.run(
            [
                sys.executable, '-m', 'pytuflow.project', 'create',
                '--name', 'testmodel',
                '--output-dir', str(tmp_path / 'out'),
                '--iter', '001',
            ],
            capture_output=True, text=True,
            cwd='/home/ellis/dev/PyTuflow',
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / 'out' / 'runs' / 'testmodel_001.tcf').exists()
