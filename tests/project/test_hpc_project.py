"""Tests for HPCProject create and insert_feature."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pytuflow.project.hpc.project import HPCProject, get_available_features, _variables_from_tcf_path
from pytuflow.project.template.manager import TemplateManager


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'my_project'


@pytest.fixture
def basic_project(project_dir):
    return HPCProject(
        name='mymodel',
        output_dir=project_dir,
        crs='EPSG:32760',
        iter='001',
        gis_format='SHP',
        map_output_formats=['XMDF'],
        create_empties=False,
    )


class TestHPCProjectValidation:
    def test_valid_project_no_errors(self, basic_project):
        assert basic_project.validate() == []

    def test_empty_name_raises(self, project_dir):
        p = HPCProject(name='', output_dir=project_dir, crs='EPSG:32760')
        errors = p.validate()
        assert any('name' in e for e in errors)


class TestHPCProjectCreate:
    def test_create_returns_output_dir(self, basic_project, project_dir):
        result = basic_project.create()
        assert result == project_dir

    def test_standard_directories_created(self, basic_project, project_dir):
        basic_project.create()
        for d in ['runs', 'model', 'bc_dbase', 'results', 'check', 'runs/log']:
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
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', map_output_formats=['XMDF', 'SHP'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Map Output Format == XMDF SHP' in tcf_text
        assert tcf_text.count('Map Output Format ==') == 1, \
            "Map Output Format should appear only once"

    def test_tcf_output_formats_per_format_settings(self, project_dir):
        """output_formats dict generates a single Map Output Format line plus per-format settings."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', output_formats={
            'XMDF': {'interval': 60, 'data_types': ['h', 'v', 'd']},
            'TIF':  {'interval': 0},
        })
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Map Output Format == XMDF TIF' in tcf_text
        assert tcf_text.count('Map Output Format ==') == 1
        assert 'XMDF Map Output Interval == 60' in tcf_text
        assert 'XMDF Map Output Data Types == h v d' in tcf_text
        assert 'TIF Map Output Interval == 0' in tcf_text

    def test_tcf_default_output_formats_has_data_types(self, project_dir):
        """Default XMDF output config includes Map Output Data Types."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760')
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'XMDF Map Output Data Types' in tcf_text

    def test_tcf_directive_lines_removed(self, basic_project, project_dir):
        basic_project.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert '##IF' not in tcf_text
        assert '##ENDIF##' not in tcf_text
        assert '##LOOP' not in tcf_text
        assert '##ENDLOOP##' not in tcf_text

    def test_validation_error_raises(self, project_dir):
        p = HPCProject(name='', output_dir=project_dir, crs='EPSG:32760')
        with pytest.raises(ValueError):
            p.create()


class TestHPCProjectWithEstryfeature:
    def test_ecf_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['estry'])
        p.create()
        assert (project_dir / 'model' / 'mymodel_001.ecf').exists()

    def test_tcf_contains_estry_command(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['estry'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert 'Estry Control File' in tcf_text
        # Should be uncommented (active feature)
        lines = [l for l in tcf_text.splitlines() if 'Estry Control File' in l]
        assert any(not l.strip().startswith('!') for l in lines)

    def test_tcf_no_estry_when_inactive(self, project_dir):
        """Without estry feature, estry line should be absent from TCF (template omits it)."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        # Template uses ##IF feature:estry## — line should be absent entirely
        active_lines = [l for l in tcf_text.splitlines()
                        if 'Estry Control File' in l and not l.strip().startswith('!')]
        assert not active_lines, "Estry Control File should not be active when feature is off"


class TestHPCProjectWithSoilsfeature:
    def test_soils_file_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['soils'])
        p.create()
        assert (project_dir / 'model' / 'mymodel_soils.tsoilf').exists()

    def test_tcf_contains_soils_command(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['soils'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Read Soils File' in l]
        assert any(not l.strip().startswith('!') for l in lines)


class TestHPCProjectWithEventsfeature:
    def test_tef_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['events'])
        p.create()
        assert (project_dir / 'runs' / 'mymodel_events.tef').exists()

    def test_tcf_events_uncommented_when_active(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['events'])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        lines = [l for l in tcf_text.splitlines() if 'Event File' in l]
        assert any(not l.strip().startswith('!') for l in lines)

    def test_tcf_events_absent_when_inactive(self, project_dir):
        """Without events feature, Event File line should be absent from TCF."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        active_lines = [l for l in tcf_text.splitlines()
                        if 'Event File' in l and not l.strip().startswith('!')]
        assert not active_lines, "Event File should not be active when feature is off"


class TestHPCProjectInsertPoint:
    def test_insert_point_not_in_tcf(self, project_dir):
        """##INSERT_POINT is a silent no-op — must NOT appear in rendered output."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760')
        p.create()
        tcf_text = (project_dir / 'runs' / 'mymodel_001.tcf').read_text()
        assert '##INSERT_POINT' not in tcf_text


class TestHPCProjectUnknownfeature:
    def test_unknown_feature_raises(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['nonexistent'])
        with pytest.raises(ValueError, match="Unknown feature"):
            p.create()


class TestGetAvailablefeatures:
    def test_returns_all_features(self):
        features = get_available_features()
        expected = {'estry', 'quadtree', 'soils', 'ad', 'toc', 'rf', 'events', 'sgs', 'po', 'tutorial', 'swmm'}
        assert set(features.keys()) == expected

    def test_features_have_name(self):
        features = get_available_features()
        for name, cls in features.items():
            assert cls.NAME == name

    def test_features_have_display_name(self):
        features = get_available_features()
        for name, cls in features.items():
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


class TestHPCBasefeatureApplyToControlFiles:
    """Tests for HPCBasefeature.apply_to_control_files logic."""

    def test_apply_skips_if_already_present(self, project_dir):
        """If command already exists in TCF, apply_to_control_files should skip."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF

        # Create project with estry already active
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['estry'])
        p.create()

        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'
        tcf = TCF(tcf_path)
        before_lines = list(tcf.find_input(lhs='estry control file', recursive=False))

        # Apply again — should be a no-op
        feature = Estryfeature()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'tcf': tcf}, variables)

        after_lines = list(tcf.find_input(lhs='estry control file', recursive=False))
        assert len(before_lines) == len(after_lines)

    def test_apply_inserts_via_placement_rule(self, project_dir):
        """apply_to_control_files uses placement_rule to find the last control-file command."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF

        # Create bare-bones project (no estry)
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'
        tcf = TCF(tcf_path)

        # No INSERT_POINT comment should exist (directive is now a silent no-op)
        assert not tcf.find_input(
            filter_by='##INSERT_POINT control_files##', comments=True, recursive=False
        ), "INSERT_POINT comment must not appear in rendered TCF"

        # Apply estry feature — should insert via placement_rule
        (project_dir / 'model').mkdir(parents=True, exist_ok=True)
        feature = Estryfeature()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'tcf': tcf}, variables)
        tcf.write('inplace')

        tcf2 = TCF(tcf_path)
        active = tcf2.find_input(lhs='estry control file', recursive=False)
        assert active, "Estry Control File should have been inserted via placement rule"

    def test_apply_uncomments_manually_added_comment(self, tmp_path):
        """apply_to_control_files can uncomment an existing commented line."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF

        # Write a minimal TCF with a commented Estry line (simulating a hand-edited file)
        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()  # needed so TCF.write() can create the ECF
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        tcf_path.write_text(
            'Solution scheme == HPC\n'
            'Geometry Control File == ..\\model\\mymodel_001.tgc\n'
            '! Estry Control File == ..\\model\\mymodel_001.ecf\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        feature = Estryfeature()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'tcf': tcf}, variables)
        tcf.write('inplace')

        tcf2 = TCF(tcf_path)
        active = tcf2.find_input(lhs='estry control file', recursive=False)
        assert active, "Estry Control File should be uncommented"

    def test_partial_block_some_commands_exist(self, tmp_path):
        """Commands that already exist are skipped individually; missing ones are inserted."""
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        from pytuflow import TCF

        # Create a minimal feature-like block with two real commands
        class TwoCommandfeature(HPCBaseFeature):
            NAME = '_test'
            DISPLAY_NAME = 'Test'
            def _get_config(self):
                return {
                    'command_blocks': [{
                        'id': 'two_cmds',
                        'target_cf': 'tcf',
                        'insert_after_lhs': 'Solution Scheme',
                        'commands': [
                            'Cmd One == value_one',
                            'Cmd Two == value_two',
                        ]
                    }]
                }

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        tcf_path = tcf_dir / 'test_001.tcf'
        # 'Cmd One' already present; 'Cmd Two' is absent
        tcf_path.write_text(
            'Solution Scheme == HPC\n'
            'Cmd One == value_one\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        TwoCommandfeature().apply_to_control_files({'tcf': tcf}, {})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        assert content.count('Cmd One') == 1, "Cmd One should appear exactly once"
        assert 'Cmd Two' in content, "Cmd Two should have been inserted"

    def test_partial_block_some_commands_commented(self, tmp_path):
        """Commented commands are uncommented individually; others are inserted."""
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        from pytuflow import TCF

        class TwoCommandfeature(HPCBaseFeature):
            NAME = '_test'
            DISPLAY_NAME = 'Test'
            def _get_config(self):
                return {
                    'command_blocks': [{
                        'id': 'two_cmds',
                        'target_cf': 'tcf',
                        'insert_after_lhs': 'Solution Scheme',
                        'commands': [
                            'Cmd Alpha == 1',
                            'Cmd Beta == 2',
                        ]
                    }]
                }

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        tcf_path = tcf_dir / 'test_001.tcf'
        # 'Cmd Alpha' is commented; 'Cmd Beta' is absent
        tcf_path.write_text(
            'Solution Scheme == HPC\n'
            '! Cmd Alpha == 1\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        TwoCommandfeature().apply_to_control_files({'tcf': tcf}, {})
        tcf.write('inplace')

        tcf2 = TCF(tcf_path)
        assert tcf2.find_input(lhs='cmd alpha', recursive=False), "Cmd Alpha should be uncommented"
        assert tcf2.find_input(lhs='cmd beta', recursive=False), "Cmd Beta should be inserted"

    def test_decorator_comments_not_inserted_when_all_commands_exist(self, tmp_path):
        """Section-header decorator comments are NOT inserted when all real commands exist."""
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        from pytuflow import TCF

        class Decoratedfeature(HPCBaseFeature):
            NAME = '_test'
            DISPLAY_NAME = 'Test'
            def _get_config(self):
                return {
                    'command_blocks': [{
                        'id': 'decorated',
                        'target_cf': 'tcf',
                        'insert_after_lhs': 'Solution Scheme',
                        'commands': [
                            '!_______',
                            '! SECTION HEADER',
                            'My Command == value',
                        ]
                    }]
                }

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        tcf_path = tcf_dir / 'test_001.tcf'
        # 'My Command' already present
        tcf_path.write_text(
            'Solution Scheme == HPC\n'
            'My Command == value\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        Decoratedfeature().apply_to_control_files({'tcf': tcf}, {})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        assert content.count('SECTION HEADER') == 0, \
            "Decorator comment must not be inserted when all commands already exist"

    def test_trailing_comment_after_real_command_is_inserted(self, tmp_path):
        """Comment lines that follow a real command (e.g. placeholders) are always inserted."""
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        from pytuflow import TCF

        class TrailingCommentfeature(HPCBaseFeature):
            NAME = '_test'
            DISPLAY_NAME = 'Test'
            def _get_config(self):
                return {
                    'command_blocks': [{
                        'id': 'trailing',
                        'target_cf': 'tcf',
                        'insert_after_lhs': 'Solution Scheme',
                        'commands': [
                            'Real Command == 60',
                            '! Read GIS Layer == <path/to/layer>',
                        ]
                    }]
                }

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        tcf_path = tcf_dir / 'test_001.tcf'
        tcf_path.write_text('Solution Scheme == HPC\n', encoding='utf-8')

        tcf = TCF(tcf_path)
        TrailingCommentfeature().apply_to_control_files({'tcf': tcf}, {})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        assert 'Real Command == 60' in content
        assert '! Read GIS Layer == <path/to/layer>' in content, \
            "Trailing placeholder comment should be inserted after the real command"

    def test_po_feature_inserts_placeholder_comment(self, tmp_path):
        """Regression: po feature's '! Read GIS PO' placeholder must appear in the TCF."""
        from pytuflow.project.hpc.project import get_available_features
        POfeature = get_available_features()['po']
        from pytuflow import TCF

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        tcf_path = tcf_dir / 'test_001.tcf'
        tcf_path.write_text(
            'Output Folder == ..\\results\\\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        POfeature().apply_to_control_files({'tcf': tcf}, {'model_name': 'test', 'iter': '001'})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        assert 'Time Series Output Interval' in content
        assert '! Read GIS PO' in content, \
            "Placeholder '! Read GIS PO' must be inserted after Time Series Output Interval"


class TestParseFilter:
    """Unit tests for the _parse_filter helper."""

    def test_plain_string_unchanged(self):
        from pytuflow.project.hpc.features._base import _parse_filter
        pattern, is_regex, flags = _parse_filter("estry control file")
        assert pattern == "estry control file"
        assert is_regex is False
        assert flags == 0

    def test_regex_basic(self):
        import re
        from pytuflow.project.hpc.features._base import _parse_filter
        pattern, is_regex, flags = _parse_filter("/^SGS$/i")
        assert pattern == "^SGS$"
        assert is_regex is True
        assert flags == re.IGNORECASE

    def test_regex_multiple_flags(self):
        import re
        from pytuflow.project.hpc.features._base import _parse_filter
        pattern, is_regex, flags = _parse_filter("/^set soil\\s*==/im")
        assert pattern == "^set soil\\s*=="
        assert is_regex is True
        assert flags == re.IGNORECASE | re.MULTILINE

    def test_regex_no_flags(self):
        from pytuflow.project.hpc.features._base import _parse_filter
        pattern, is_regex, flags = _parse_filter("/^exact$/")
        assert pattern == "^exact$"
        assert is_regex is True
        assert flags == 0


class TestAutoCommentDetection:
    """Tests for automatic detection of commented-out command variants."""

    def test_auto_uncomments_exact_command(self, tmp_path):
        """Auto-detection finds and uncomments '! Estry Control File ==' precisely."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        tcf_path.write_text(
            'Geometry Control File == ..\\model\\mymodel_001.tgc\n'
            '! Estry Control File == ..\\model\\mymodel_001.ecf\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        Estryfeature().apply_to_control_files({'tcf': tcf}, {'model_name': 'mymodel', 'iter': '001'})
        tcf.write('inplace')

        tcf2 = TCF(tcf_path)
        assert tcf2.find_input(lhs='estry control file', recursive=False), \
            "Estry Control File should be uncommented"

    def test_auto_detect_avoids_false_prefix_match(self, tmp_path):
        """Auto-detection must NOT match 'Set Soil Layer 2' when looking for 'Set Soil'."""
        from pytuflow.project.hpc.project import get_available_features
        Soilsfeature = get_available_features()['soils']
        from pytuflow import TGC

        tgc_dir = tmp_path / 'model'
        tgc_dir.mkdir()
        tgc_path = tgc_dir / 'mymodel_001.tgc'
        tgc_path.write_text(
            'Set Mat == 1\n'
            '! Set Soil Layer 2 == 1\n',
            encoding='utf-8',
        )

        tgc = TGC(tgc_path)
        Soilsfeature().apply_to_control_files({'tgc': tgc}, {'model_name': 'mymodel', 'iter': '001'})
        tgc.write('inplace')

        content = tgc_path.read_text(encoding='utf-8')
        assert '! Set Soil Layer 2' in content, "Set Soil Layer 2 should remain commented"

    def test_no_commented_lhs_in_feature_jsons(self):
        """No feature JSON should contain a 'commented_lhs' key — it is now auto-derived."""
        from pytuflow.project.template.manager import TemplateManager
        from pytuflow.project.hpc.project import get_available_features
        manager = TemplateManager('hpc')
        for name in get_available_features():
            cfg = manager.get_feature_config(name)
            for block in cfg.get('command_blocks', []):
                assert 'commented_lhs' not in block, \
                    f"feature '{name}' block '{block.get('id')}' still has deprecated 'commented_lhs'"


class TestPlacementRules:
    """Tests for the rules.json placement-rule system."""

    def test_rules_json_loadable(self):
        from pytuflow.project.template.manager import TemplateManager
        manager = TemplateManager('hpc')
        rules = manager.get_rules()
        assert 'hpc_control_files' in rules
        assert 'commands' in rules['hpc_control_files']
        assert len(rules['hpc_control_files']['commands']) > 0
        assert rules['hpc_control_files'].get('rule') == 'after'

    def test_control_files_rule_contains_expected_lhs(self):
        from pytuflow.project.template.manager import TemplateManager
        manager = TemplateManager('hpc')
        rules = manager.get_rules()
        commands = rules['hpc_control_files']['commands']
        for expected in ['Geometry Control File', 'BC Control File', 'Read Materials File']:
            assert expected in commands, f"'{expected}' missing from hpc_control_files rule"

    def test_regex_command_in_rules_is_recognised(self, tmp_path):
        """A /pattern/flags entry in a rule's commands list is used as a regex match."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF
        import pytuflow.project.template.manager as mgr_mod

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        tcf_path.write_text(
            'Geometry Control File == ..\\model\\mymodel_001.tgc\n'
            'Read Materials File == ..\\model\\mymodel_mat.csv\n',
            encoding='utf-8',
        )

        # Override rule to use a regex entry for "Read Materials File"
        fake_rules = {
            'hpc_control_files': {
                'rule': 'after',
                'commands': ['/^read materials file$/i'],
            }
        }
        original_get_rules = mgr_mod.TemplateManager.get_rules
        mgr_mod.TemplateManager.get_rules = lambda self: fake_rules
        try:
            tcf = TCF(tcf_path)
            Estryfeature().apply_to_control_files({'tcf': tcf}, {'model_name': 'mymodel', 'iter': '001'})
            tcf.write('inplace')
        finally:
            mgr_mod.TemplateManager.get_rules = original_get_rules

        content = tcf_path.read_text(encoding='utf-8')
        ecf_pos = content.lower().find('estry control file')
        mat_pos = content.lower().find('read materials file')
        assert ecf_pos > mat_pos, "Estry should be inserted after Read Materials File via regex rule"

    def test_feature_jsons_use_placement_rule(self):
        """All features that previously used insert_point now use placement_rule."""
        from pytuflow.project.template.manager import TemplateManager
        manager = TemplateManager('hpc')
        for name in ['estry', 'soils', 'ad', 'rf', 'quadtree', 'toc']:
            cfg = manager.get_feature_config(name)
            for block in cfg.get('command_blocks', []):
                assert 'insert_point' not in block, (
                    f"feature '{name}' block '{block.get('id')}' still uses deprecated 'insert_point'"
                )

    def test_placement_rule_inserts_after_last_cf_command(self, tmp_path):
        """Placement rule inserts after the last matching command in the CF section."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        # A TCF with existing control file commands but no estry
        tcf_path.write_text(
            'Geometry Control File == ..\\model\\mymodel_001.tgc\n'
            'BC Control File == ..\\model\\mymodel_001.tbc\n'
            'BC Database == ..\\bc_dbase\\bc_dbase.csv\n'
            'Read Materials File == ..\\model\\mymodel_mat.csv\n',
            encoding='utf-8',
        )

        tcf = TCF(tcf_path)
        feature = Estryfeature()
        feature.apply_to_control_files({'tcf': tcf}, {'model_name': 'mymodel', 'iter': '001'})
        tcf.write('inplace')

        content = tcf_path.read_text(encoding='utf-8')
        ecf_pos = content.lower().find('estry control file')
        mat_pos = content.lower().find('read materials file')
        assert ecf_pos > mat_pos, "Estry Control File should appear after Read Materials File"

    def test_unsupported_rule_type_raises(self, tmp_path):
        """An unimplemented rule type in rules.json raises NotImplementedError."""
        from pytuflow.project.hpc.project import get_available_features
        Estryfeature = get_available_features()['estry']
        from pytuflow import TCF
        import pytuflow.project.template.manager as mgr_mod

        tcf_dir = tmp_path / 'runs'
        tcf_dir.mkdir()
        (tmp_path / 'model').mkdir()
        tcf_path = tcf_dir / 'mymodel_001.tcf'
        tcf_path.write_text(
            'Geometry Control File == ..\\model\\mymodel_001.tgc\n'
            'Read Materials File == ..\\model\\mymodel_mat.csv\n',
            encoding='utf-8',
        )

        fake_rules = {'hpc_control_files': {'rule': 'inbetween', 'commands': ['Read Materials File']}}
        original_get_rules = mgr_mod.TemplateManager.get_rules

        mgr_mod.TemplateManager.get_rules = lambda self: fake_rules
        try:
            tcf = TCF(tcf_path)
            feature = Estryfeature()
            with pytest.raises(NotImplementedError, match="'inbetween'.*not implemented"):
                feature.apply_to_control_files({'tcf': tcf}, {'model_name': 'mymodel', 'iter': '001'})
        finally:
            mgr_mod.TemplateManager.get_rules = original_get_rules


class TestExistenceCheck:
    """Tests for the existence_check atomic block-guard feature."""

    def _make_tbc(self, tmp_path, content: str):
        from pytuflow import TBC
        tbc_path = tmp_path / 'mymodel_001.tbc'
        tbc_path.write_text(content, encoding='utf-8')
        return TBC(tbc_path), tbc_path

    def _make_block(self, existence_check: str, commands: list[str]) -> dict:
        return {
            'target_cf': 'tbc',
            'existence_check': existence_check,
            'commands': commands,
        }

    def _feature(self):
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        m = HPCBaseFeature.__new__(HPCBaseFeature)
        return m

    def test_comment_guard_inserts_when_absent(self, tmp_path):
        """Block is inserted when the comment sentinel is not present."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            '! BOUNDARY CONDITIONS\nRead GIS BC == ..\\model\\inflow_L.shp\n',
        )
        block = self._make_block(
            '! 1D/2D LINKING',
            ['! 1D/2D LINKING', 'Read GIS BC == ..\\model\\2d_bc_L.shp'],
        )
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert '1D/2D LINKING' in content
        assert content.count('Read GIS BC') == 2

    def test_comment_guard_skips_when_present(self, tmp_path):
        """Block is skipped entirely when the comment sentinel already exists."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            '! BOUNDARY CONDITIONS\nRead GIS BC == ..\\model\\inflow_L.shp\n'
            '! 1D/2D LINKING\nRead GIS BC == ..\\model\\2d_bc_L.shp\n',
        )
        block = self._make_block(
            '! 1D/2D LINKING',
            ['! 1D/2D LINKING', 'Read GIS BC == ..\\model\\2d_bc_L.shp'],
        )
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Read GIS BC') == 2  # still only 2 — no duplicate inserted

    def test_lhs_guard_inserts_when_absent(self, tmp_path):
        """Block with an lhs existence_check is inserted when sentinel command is absent."""
        tbc, tbc_path = self._make_tbc(tmp_path, '')
        block = self._make_block(
            'Read GIS BC Linking',
            ['Read GIS BC Linking == ..\\model\\linking_L.shp'],
        )
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert 'Read GIS BC Linking' in content

    def test_lhs_guard_skips_when_present(self, tmp_path):
        """Block with an lhs existence_check is skipped when sentinel command exists."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            'Read GIS BC Linking == ..\\model\\linking_L.shp\n',
        )
        block = self._make_block(
            'Read GIS BC Linking',
            ['Read GIS BC Linking == ..\\model\\linking_L.shp'],
        )
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Read GIS BC Linking') == 1  # not duplicated


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

    def test_list_features(self, capsys):
        import sys
        from pytuflow.project.__main__ import cmd_list_features
        cmd_list_features(None)
        captured = capsys.readouterr()
        assert 'estry' in captured.out

    def test_create_via_main(self, tmp_path):
        import subprocess, sys
        result = subprocess.run(
            [
                sys.executable, '-m', 'pytuflow.project', 'create',
                '--engine', 'hpc',
                '--name', 'testmodel',
                '--output-dir', str(tmp_path / 'out'),
                '--crs', 'EPSG:32760',
                '--iter', '001',
            ],
            capture_output=True, text=True,
            cwd='/home/ellis/dev/PyTuflow',
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / 'out' / 'runs' / 'testmodel_001.tcf').exists()


class TestfeatureJsonConfig:
    """Tests for feature JSON config loading via TemplateManager."""

    def test_feature_config_loaded(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        config = manager.get_feature_config('estry')
        assert config['name'] == 'estry'
        assert 'command_blocks' in config
        assert 'template_files' in config

    def test_soils_config_has_tgc_block(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        config = manager.get_feature_config('soils')
        targets = [b['target_cf'] for b in config['command_blocks']]
        assert 'tcf' in targets
        assert 'tgc' in targets

    def test_feature_config_cached(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        manager.init_cache()
        cached_path = manager._cache_features_dir / 'estry.json'
        assert cached_path.exists()

    def test_feature_config_cache_reset(self, tmp_path, monkeypatch):
        import json
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        manager.init_cache()
        # Modify cached config
        cached_path = manager._cache_features_dir / 'estry.json'
        cached_path.write_text('{"name": "modified"}')
        # Reset should restore original
        manager.reset_cache()
        with open(cached_path) as f:
            data = json.load(f)
        assert data['name'] == 'estry'

    def test_unknown_feature_returns_empty(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        config = manager.get_feature_config('nonexistent')
        assert config == {}

    def test_list_feature_configs(self, tmp_path, monkeypatch):
        import pytuflow.project.template.manager as mgr_mod
        monkeypatch.setattr(mgr_mod, 'CACHE_ROOT', tmp_path / 'cache')
        manager = TemplateManager('hpc')
        names = [x[0] for x in manager.list_feature_configs()]
        assert 'estry' in names
        assert 'soils' in names


class TestSoilsMultiCFfeature:
    """Tests that the soils feature applies commands to both TCF and TGC."""

    def test_soils_adds_set_soil_to_tgc(self, project_dir):
        """Creating a project with soils should result in Set Soil in TGC."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=['soils'])
        p.create()
        tgc_text = (project_dir / 'model' / 'mymodel_001.tgc').read_text()
        active_lines = [l for l in tgc_text.splitlines()
                        if 'Set Soil' in l and not l.strip().startswith('!')]
        assert active_lines, "TGC should contain active Set Soil command"

    def test_soils_tgc_content_without_soils(self, project_dir):
        """Without soils feature, TGC should have no soil section."""
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()
        tgc_text = (project_dir / 'model' / 'mymodel_001.tgc').read_text()
        assert 'Set Soil' not in tgc_text

    def test_insert_soils_into_existing_project(self, project_dir):
        """Inserting soils into an existing bare-bones project modifies both TCF and TGC."""
        from pytuflow import TCF, TGC

        # Create bare-bones project
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760')
        p.create()

        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'
        tgc_path = project_dir / 'model' / 'mymodel_001.tgc'

        # Sanity check: soils not present yet
        tcf_before = TCF(tcf_path)
        assert not tcf_before.find_input(lhs='read soils file', recursive=False)

        # Insert soils feature
        HPCProject.insert_feature_into('soils', tcf_path)

        # TCF should now have Read Soils File
        tcf_after = TCF(tcf_path)
        assert tcf_after.find_input(lhs='read soils file', recursive=False), \
            "TCF should have Read Soils File after insert"

        # TGC should now have Set Soil
        tgc_after = TGC(tgc_path)
        soil_inps = tgc_after.find_input(lhs='set soil', recursive=False)
        assert soil_inps, "TGC should have Set Soil after insert"

        # tsoilf file should have been created
        assert (project_dir / 'model' / 'mymodel_soils.tsoilf').exists()

    def test_insert_soils_idempotent(self, project_dir):
        """Inserting soils twice should not duplicate commands."""
        from pytuflow import TCF

        p = HPCProject('mymodel', project_dir, crs='EPSG:32760')
        p.create()
        tcf_path = project_dir / 'runs' / 'mymodel_001.tcf'

        HPCProject.insert_feature_into('soils', tcf_path)
        HPCProject.insert_feature_into('soils', tcf_path)

        tcf = TCF(tcf_path)
        soils_inps = tcf.find_input(lhs='read soils file', recursive=False)
        assert len(soils_inps) == 1, "Read Soils File should appear exactly once"


class TestTuflowEmptyFiles:
    """Tests for empty GIS file creation."""

    def test_empties_dir_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='GPKG', create_empties=True)
        p.create()
        assert (project_dir / 'model' / 'gis' / 'empty').is_dir()

    def test_empties_created_for_gpkg(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='GPKG', create_empties=True)
        p.create()
        empties_dir = project_dir / 'model' / 'gis' / 'empty'
        gpkg_files = list(empties_dir.glob('*.gpkg'))
        assert len(gpkg_files) > 0, 'Expected GPKG empty files to be created'

    def test_no_empties_when_disabled(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='GPKG', create_empties=False)
        p.create()
        assert not (project_dir / 'model' / 'gis' / 'empty').exists()

    def test_empty_schema_fields(self, tmp_path):
        """Each TuflowEmptyType should resolve its schema correctly."""
        from pytuflow.project.template.empties import TuflowEmptyType
        et = TuflowEmptyType('hpc', '1d_nwk', 'PL', 'GPKG')
        schema = et.get_schema('1d_nwk')
        assert schema is not None
        names = [f['name'] for f in schema]
        assert 'ID' in names
        assert 'Type' in names

    def test_empty_schema_append_inheritance(self, tmp_path):
        """1d_nwke extends 1d_nwk with extra fields appended."""
        from pytuflow.project.template.empties import TuflowEmptyType
        et = TuflowEmptyType('hpc', '1d_nwke', 'PL', 'GPKG')
        base_schema = et.get_schema('1d_nwk')
        ext_schema = et.get_schema('1d_nwke')
        assert ext_schema is not None
        assert len(ext_schema) > len(base_schema)
        ext_names = [f['name'] for f in ext_schema]
        assert 'eS1' in ext_names

    def test_empty_schema_replace_inheritance(self, tmp_path):
        """1d_nwkb replaces the pBlockage field in 1d_nwk."""
        from pytuflow.project.template.empties import TuflowEmptyType
        et = TuflowEmptyType('hpc', '1d_nwkb', 'PL', 'GPKG')
        schema = et.get_schema('1d_nwkb')
        assert schema is not None
        pb = next(f for f in schema if f['name'] == 'pBlockage')
        assert pb['field_type'] == 'string', 'pBlockage should be replaced with string type'

    def test_geom_normalization(self):
        """Multi-char geom elements like ['PL'] are split into individual chars."""
        from pytuflow.project.template.empties import TuflowEmptyType
        et = TuflowEmptyType('hpc', '2d_po', 'PLR', 'GPKG')
        assert et.geom == ['P', 'L', 'R']


class TestProjectionFile:
    """Tests for projection/spatial-database file creation."""

    def test_shp_projection_file_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='SHP', create_empties=False)
        p.create()
        assert (project_dir / 'model' / 'gis' / 'projection.shp').exists()

    def test_mif_projection_file_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='MIF', create_empties=False)
        p.create()
        assert (project_dir / 'model' / 'gis' / 'projection.mif').exists()

    def test_gpkg_central_db_created(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='GPKG', create_empties=False)
        p.create()
        assert (project_dir / 'model' / 'gis' / 'mymodel_001.gpkg').exists()

    def test_tcf_shp_projection_command(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='SHP', create_empties=False)
        p.create()
        tcf = (project_dir / 'runs' / 'mymodel_001.tcf').read_text(encoding='utf-8')
        assert 'SHP Projection ==' in tcf
        assert 'MI Projection ==' not in tcf
        assert 'GPKG Projection ==' not in tcf

    def test_tcf_gpkg_projection_and_spatial_db_commands(self, project_dir):
        p = HPCProject('mymodel', project_dir, crs='EPSG:32760', gis_format='GPKG', create_empties=False)
        p.create()
        tcf = (project_dir / 'runs' / 'mymodel_001.tcf').read_text(encoding='utf-8')
        assert 'GPKG Projection ==' in tcf
        assert 'Spatial Database ==' in tcf
        assert 'SHP Projection ==' not in tcf


class TestAllowMultiple:
    """Tests for the allow_multiple flag in _apply_block."""

    def _make_tbc(self, tmp_path, content: str):
        from pytuflow import TBC
        tbc_path = tmp_path / 'mymodel_001.tbc'
        tbc_path.write_text(content, encoding='utf-8')
        return TBC(tbc_path), tbc_path

    def _feature(self):
        from pytuflow.project.hpc.features._base import HPCBaseFeature
        return HPCBaseFeature.__new__(HPCBaseFeature)

    def test_allow_multiple_inserts_despite_existing_lhs(self, tmp_path):
        """With allow_multiple, a second command with the same LHS is inserted."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            'Structure == weir, 1, 2\n',
        )
        block = {
            'target_cf': 'tbc',
            'allow_multiple': True,
            'commands': ['Structure == culvert, 3, 4'],
        }
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Structure ==') == 2

    def test_allow_multiple_false_skips_duplicate_lhs(self, tmp_path):
        """Without allow_multiple, a command whose LHS already exists is skipped."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            'Structure == weir, 1, 2\n',
        )
        block = {
            'target_cf': 'tbc',
            'allow_multiple': False,
            'commands': ['Structure == culvert, 3, 4'],
        }
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Structure ==') == 1

    def test_allow_multiple_with_existence_check_idempotent(self, tmp_path):
        """With existence_check + allow_multiple, re-inserting the same feature is a no-op."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            'Structure == weir, 1, 2\n',
        )
        block = {
            'target_cf': 'tbc',
            'allow_multiple': True,
            'existence_check': '/^Structure == weir/i',
            'commands': ['Structure == weir, 1, 2'],
        }
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Structure ==') == 1  # idempotent

    def test_allow_multiple_different_features_both_inserted(self, tmp_path):
        """structweir and structculvert can both insert Structure == independently."""
        tbc, tbc_path = self._make_tbc(tmp_path, '')
        feature = self._feature()

        weir_block = {
            'target_cf': 'tbc',
            'allow_multiple': True,
            'commands': ['Structure == weir, 1, 2'],
        }
        culvert_block = {
            'target_cf': 'tbc',
            'allow_multiple': True,
            'commands': ['Structure == culvert, 3, 4'],
        }
        feature._apply_block(tbc, weir_block, {})
        feature._apply_block(tbc, culvert_block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        assert content.count('Structure ==') == 2
        assert 'weir' in content
        assert 'culvert' in content

    def test_allow_multiple_does_not_uncomment_existing(self, tmp_path):
        """With allow_multiple, a commented version is not uncommented — a fresh line is added."""
        tbc, tbc_path = self._make_tbc(
            tmp_path,
            '! Structure == weir, 1, 2\n',
        )
        block = {
            'target_cf': 'tbc',
            'allow_multiple': True,
            'commands': ['Structure == culvert, 3, 4'],
        }
        self._feature()._apply_block(tbc, block, {})
        tbc.write('inplace')
        content = tbc_path.read_text(encoding='utf-8')
        # The commented weir line stays commented; culvert is added fresh
        assert '! Structure == weir' in content
        assert 'Structure == culvert' in content
