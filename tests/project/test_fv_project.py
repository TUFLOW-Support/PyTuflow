"""Tests for FVProject create and feature framework."""
import pytest
from pathlib import Path
import re

from pytuflow.project.fv.project import FVProject, get_available_features


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'fv_project'


@pytest.fixture
def basic_project(project_dir):
    return FVProject(
        name='mymodel',
        output_dir=project_dir,
        crs='EPSG:32760',
        gis_format='SHP',
        create_empties=False,
    )


class TestFVProjectValidation:
    def test_valid_project_no_errors(self, basic_project):
        assert basic_project.validate() == []

    def test_empty_name_raises(self, project_dir):
        p = FVProject(name='', output_dir=project_dir, crs='EPSG:32760')
        errors = p.validate()
        assert any('name' in e for e in errors)

    def test_gpkg_not_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='GPKG')
        errors = p.validate()
        assert any('GPKG' in e for e in errors)

    def test_shp_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='SHP')
        assert p.validate() == []

    def test_mif_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='MIF')
        assert p.validate() == []

    def test_gpkg_raises_on_create(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='GPKG')
        with pytest.raises(ValueError, match='GPKG'):
            p.create()


class TestFVProjectCreate:
    def test_create_returns_output_dir(self, basic_project, project_dir):
        result = basic_project.create()
        assert result == project_dir

    def test_standard_directories_created(self, basic_project, project_dir):
        basic_project.create()
        for d in ['runs', 'model', 'model/geo', 'model/gis', 'bc_dbase', 'results', 'check', 'runs/log']:
            assert (project_dir / d).is_dir(), f"Missing directory: {d}"

    def test_fvc_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_bc_dbase_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'bc_dbase' / 'bc_dbase.csv').exists()

    def test_fvc_contains_model_name(self, basic_project, project_dir):
        basic_project.create()
        # iter and model_name substitution: template filename was rendered
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_fvc_contains_gis_format(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'GIS FORMAT == SHP' in fvc_text

    def test_fvc_shp_projection_present(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'SHP Projection' in fvc_text

    def test_fvc_mi_projection_absent_for_shp(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'MI Projection' not in fvc_text

    def test_fvc_mif_projection_present_for_mif(self, project_dir):
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', gis_format='MIF', create_empties=False,
        )
        p.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'MI Projection' in fvc_text
        assert 'SHP Projection' not in fvc_text

    def test_projection_file_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'model' / 'gis' / 'projection.shp').exists()

    def test_no_gpkg_projection_file_for_shp(self, basic_project, project_dir):
        basic_project.create()
        gpkg_files = list((project_dir / 'model' / 'gis').glob('*.gpkg'))
        assert gpkg_files == []

    def test_fvc_slashes_normalized(self, basic_project, project_dir):
        import os
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        sep = os.sep
        if sep == '/':
            assert '\\' not in fvc_text
        else:
            assert '/' not in fvc_text.replace('\r\n', '\n')

    def test_no_map_output_formats_in_fvc(self, basic_project, project_dir):
        """FV outputs are features — Map Output Format command must not appear."""
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'Map Output Format' not in fvc_text


class TestFVProjectSettings:
    def test_fv_defaults_loaded(self, project_dir):
        """FV-specific defaults (spherical, latitude) should be available."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'spherical' in p.settings._settings
        assert 'latitude' in p.settings._settings

    def test_hpc_defaults_not_loaded(self, project_dir):
        """HPC-specific defaults (cell_size, engine) should not appear in FV settings."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'cell_size' not in p.settings._settings
        assert 'engine' not in p.settings._settings

    def test_no_output_formats_in_fv_settings(self, project_dir):
        """FV settings should not have output_formats / map_output_formats."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'map_output_formats' not in p.settings._settings
        assert 'output_formats' not in p.settings._settings

    def test_gis_format_normalized_uppercase(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='shp')
        assert p.settings._settings['gis_format'] == 'SHP'


class TestFVAvailablefeatures:
    def test_get_available_features_returns_dict(self):
        features = get_available_features()
        assert isinstance(features, dict)

    def test_features_are_fv_engine_type(self):
        features = get_available_features()
        for name, cls in features.items():
            instance = cls()
            assert instance.ENGINE_TYPE == 'fv', f"{name} has wrong ENGINE_TYPE"


class TestFVProjectIter:
    def test_custom_iter(self, project_dir):
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', iter='002', create_empties=False,
        )
        p.create()
        assert (project_dir / 'runs' / 'mymodel_002.fvc').exists()


class TestFVBaseFeatureApplyToControlFiles:

    def test_apply_inserts_via_placement_rule(self, project_dir):
        """apply_to_control_files uses placement_rule to find the last control-file command."""
        from pytuflow.project.fv.project import get_available_features
        OutputNetcdf = get_available_features()['outputnc']
        from pytuflow import FVC

        # Create bare-bones project (no estry)
        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        # Apply output_nc feature — should insert via placement_rule
        (project_dir / 'model').mkdir(parents=True, exist_ok=True)
        feature = OutputNetcdf()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'fvc': fvc}, variables)
        fvc.write('inplace')

        fvc2 = FVC(fvc_path)
        active = fvc2.find_input(filter_by='^output == netcdf$', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert active, "Output == netcdf should have been inserted via placement rule"

    def test_apply_inserts_via_placement_rule_with_include_file(self, project_dir):
        """apply_to_control_files uses placement_rule to find the last control-file command."""
        from pytuflow.project.fv.project import get_available_features
        OutputNetcdf = get_available_features()['outputnc']
        from pytuflow import FVC

        # Create bare-bones project (no estry)
        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        include = FVC()
        include.fpath = project_dir / 'runs' / 'outputs.fvc'
        include.parent = fvc
        inp = include.append_input('Output == Points')
        block = inp.block_control()
        block.append_input('Read GIS PO == <path/to/3d_po.shp>')
        block.append_input('Output Parameters == h, v, d')
        block.append_input('Output Interval == 300.')
        inp = fvc.append_input('Include == outputs.fvc')
        inp.cf.append(include)

        # Apply output_nc feature — should insert via placement_rule which should end up in the include file not main fvc
        (project_dir / 'model').mkdir(parents=True, exist_ok=True)
        feature = OutputNetcdf()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'fvc': fvc}, variables)
        fvc.write('inplace')

        fvc2 = FVC(fvc_path)
        active = fvc2.find_input(filter_by='^output == netcdf$', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert not active, "Output == netcdf should not have been inserted into the main fvc"
        active = fvc2.find_input(filter_by='^output == netcdf$', recursive='similar', regex=True, regex_flags=re.IGNORECASE)
        assert active, "Output == netcdf should have been added"
        assert active[0].parent.fpath.name == 'outputs.fvc', "Output == netcdf should have been added to outputs.fvc"

    def test_apply_inserts_via_placement_rule_with_before_anchor(self, project_dir):
        """apply_to_control_files uses placement_rule to find the last control-file command."""
        from pytuflow.project.fv.project import get_available_features
        OutputFlux = get_available_features()['outputflux']
        from pytuflow import FVC

        # Create bare-bones project (no estry)
        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        # Apply outputflux feature — should insert via placement_rule which has a 'before' rule
        (project_dir / 'model').mkdir(parents=True, exist_ok=True)
        feature = OutputFlux()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'fvc': fvc}, variables)
        fvc.write('inplace')

        fvc2 = FVC(fvc_path)
        flux = fvc2.find_input(filter_by='^output == flux$', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert flux, "Output == flux should have been inserted via placement rule"
        nodestring = fvc2.find_input(filter_by='Read GIS Nodestring', recursive=False)
        assert nodestring, "Read GIS Nodestring should have been inserted via placement rule"
        iflux = fvc2.inputs.index(flux[0])
        inodestring = fvc2.inputs.index(nodestring[0])
        assert inodestring < iflux, "Read GIS Nodestring should have been placed before output == flux command"

    def test_apply_struct_via_placement_rule(self, project_dir):
        from pytuflow.project.fv.project import get_available_features
        Weir = get_available_features()['structweir']
        from pytuflow import FVC

        # Create bare-bones project (no estry)
        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        # Apply outputflux feature — should insert via placement_rule which has a 'before' rule
        (project_dir / 'model').mkdir(parents=True, exist_ok=True)
        feature = Weir()
        variables = {'model_name': 'mymodel', 'iter': '001'}
        feature.apply_to_control_files({'fvc': fvc}, variables)
        fvc.write('inplace')

        fvc2 = FVC(fvc_path)
        flux = fvc2.find_input(lhs='^structure$', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert flux, "Structure block should have been inserted via placement rule"
        weir = fvc2.find_input(filter_by='^Flux Function == Weir$', recursive='block', regex=True, regex_flags=re.IGNORECASE)
        assert weir, "Flux function == Weir should be present"
        nodestring = fvc2.find_input(filter_by='^Read GIS Notestring == <path/to/2d_ns_weir.shp>$', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert weir, "Flux function == Weir should be present"
        header = fvc.find_input(filter_by='! HYDRAULIC STRUCTURES', recursive=False, comments=True)
        assert header, "Structure header should have been inserted"
        iflux = fvc.inputs.inputs(include_hidden=True).index(flux[0])
        inodestring = fvc.inputs.inputs(include_hidden=True).index(nodestring[0])
        iheader = fvc.inputs.inputs(include_hidden=True).index(header[0])
        assert iheader < inodestring, '! HYDRAULIC STRUCTURES should be before Read GIS Nodestring '
        assert inodestring < iflux, 'Read GIS Nodestring should be before Structure =='


class TestAllowMultipleWithInstanceOverrides:
    """Tests for per-instance variable overrides on allow_multiple features."""

    def test_dict_feature_same_as_string(self, project_dir):
        """{'name': 'outputnc'} behaves identically to 'outputnc' with no overrides."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=[{'name': 'outputnc'}],
        )
        p.create()
        fvc = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'Output == netcdf' in fvc

    def test_multiple_outputnc_both_inserted(self, project_dir):
        """Two outputnc instances are both inserted with allow_multiple."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=[
                {'name': 'outputnc', 'output_interval': '3600.', 'suffix': 'HD'},
                {'name': 'outputnc', 'output_interval': '900.', 'suffix': 'TS'},
            ],
        )
        p.create()
        fvc = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert fvc.count('Output == netcdf') == 2

    def test_per_instance_variable_substituted(self, project_dir):
        """Per-instance variables are substituted into commands."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=[
                {'name': 'outputnc', 'output_interval': '600.', 'suffix': 'DETAIL'},
            ],
        )
        p.create()
        fvc = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'Output == netcdf' in fvc

    def test_plain_string_feature_still_works(self, project_dir):
        """Plain string features continue to work as before."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=['outputnc'],
        )
        p.create()
        fvc = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'Output == netcdf' in fvc

    def test_mixed_string_and_dict_features(self, project_dir):
        """Mix of plain strings and dicts works together."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=[
                'outputflux',
                {'name': 'outputnc', 'suffix': 'HD'},
                {'name': 'outputnc', 'suffix': 'WQ'},
            ],
        )
        p.create()
        fvc = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert fvc.count('Output == netcdf') == 2
        assert 'Output == flux' in fvc

    def test_unknown_feature_in_dict_raises(self, project_dir):
        """Dict with unknown feature name raises ValueError."""
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', create_empties=False,
            features=[{'name': 'nonexistent_feature'}],
        )
        with pytest.raises(ValueError, match='nonexistent_feature'):
            p.create()


class TestLoopAllFoundTargets:
    """Tests for loop_all_found_targets behaviour (subtarget_cf applied to every match)."""

    def test_wq_header_inserted_under_each_bc(self, project_dir):
        """wqm feature inserts WQ Header == under every BC == WL/Q/QS block."""
        from pytuflow.project.fv.project import get_available_features
        WQM = get_available_features()['wqm']
        from pytuflow import FVC

        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        # Add two BC == WL blocks manually so subtarget_cf has two targets
        inp1 = fvc.append_input('BC == WL')
        bc1 = inp1.block_control()
        bc1.append_input('BC Name == Boundary_1')
        inp2 = fvc.append_input('BC == Q')
        bc2 = inp2.block_control()
        bc2.append_input('BC Name == Boundary_2')

        feature = WQM()
        variables = {
            'model_name': 'mymodel', 'iter': '001',
            'wq_bc_header': 'TRACER',
            'initial_wq': '0.0',
            'output_params': 'wq',
            'output_interval': '3600.',
        }
        feature.apply_to_control_files({'fvc': fvc}, variables)

        # WQ Header == should have been inserted under each BC block (template has 1, we added 2 = 3 total)
        wq_headers = fvc.find_input(lhs='WQ Header', recursive='block')
        bc_blocks = fvc.find_input(filter_by=r'^BC == (?:WL|Q|QS)', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        assert len(wq_headers) == len(bc_blocks), (
            f"Expected one WQ Header == per BC block ({len(bc_blocks)}), got {len(wq_headers)}"
        )
        for h in wq_headers:
            assert h.value.strip() == 'TRACER'

    def test_wq_header_not_inserted_when_no_bc_blocks(self, project_dir):
        """wqm feature inserts WQ Header == under every BC block, including those in the template."""
        from pytuflow.project.fv.project import get_available_features
        WQM = get_available_features()['wqm']
        from pytuflow import FVC

        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()

        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        feature = WQM()
        variables = {
            'model_name': 'mymodel', 'iter': '001',
            'wq_bc_header': 'TRACER',
            'initial_wq': '0.0',
            'output_params': 'wq',
            'output_interval': '3600.',
        }
        feature.apply_to_control_files({'fvc': fvc}, variables)

        bc_blocks = fvc.find_input(filter_by=r'^BC == (?:WL|Q|QS)', recursive=False, regex=True, regex_flags=re.IGNORECASE)
        wq_headers = fvc.find_input(lhs='WQ Header', recursive='block')
        assert len(wq_headers) == len(bc_blocks), (
            f"Expected one WQ Header == per BC block ({len(bc_blocks)}), got {len(wq_headers)}"
        )

    def test_loop_all_found_false_only_first_target(self, project_dir):
        """When loop_all_found_targets is False a subtarget_cf only processes the first match."""
        from pytuflow.project.fv.project import get_available_features
        from pytuflow.project.fv.features._base import FVBaseFeature
        from pytuflow import FVC
        import json, tempfile, importlib

        # Patch wqm config to add loop_all_found_targets: false on the wq_bc_header block
        WQM = get_available_features()['wqm']
        feature = WQM()
        config = feature._get_config()
        # Deep-copy and patch the third block
        import copy
        patched_config = copy.deepcopy(config)
        for blk in patched_config['command_blocks']:
            if blk.get('id') == 'wq_bc_header':
                blk['loop_all_found_targets'] = False

        p = FVProject('mymodel', project_dir, crs='EPSG:32760', features=[])
        p.create()
        fvc_path = project_dir / 'runs' / 'mymodel_001.fvc'
        fvc = FVC(fvc_path)

        inp1 = fvc.append_input('BC == WL')
        bc1 = inp1.block_control()
        bc1.append_input('BC Name == Boundary_1')
        inp2 = fvc.append_input('BC == Q')
        bc2 = inp2.block_control()
        bc2.append_input('BC Name == Boundary_2')

        # Monkey-patch _get_config to return the patched version
        feature._get_config = lambda: patched_config
        variables = {
            'model_name': 'mymodel', 'iter': '001',
            'wq_bc_header': 'TRACER',
            'initial_wq': '0.0',
            'output_params': 'wq',
            'output_interval': '3600.',
        }
        feature.apply_to_control_files({'fvc': fvc}, variables)

        wq_headers = fvc.find_input(lhs='WQ Header', recursive='block')
        assert len(wq_headers) == 1, (
            f"With loop_all_found_targets=False, expected only 1 WQ Header ==, got {len(wq_headers)}"
        )
